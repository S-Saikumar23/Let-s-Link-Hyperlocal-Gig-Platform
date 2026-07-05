"""
Dispute resolution routes.
Requester or Provider can raise a dispute → Admin reviews → Resolved.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models import Dispute, Task, User, Payment, DisputeStatus, EscrowStatus, TaskStatus
from auth import get_current_user

router = APIRouter(prefix="/disputes", tags=["Disputes"])


# ── Schemas ───────────────────────────────────────────────────

class RaiseDisputeRequest(BaseModel):
    task_id: str
    reason: str        # damage, incomplete, fraud, overcharge, no_show, other
    description: str
    evidence_urls: Optional[str] = None  # Comma-separated image URLs


class ResolveDisputeRequest(BaseModel):
    resolution: str    # "requester" or "provider"
    notes: str


# ── Raise Dispute ─────────────────────────────────────────────

@router.post("/raise", status_code=status.HTTP_201_CREATED)
async def raise_dispute(
    data: RaiseDisputeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Raise a dispute on a task. Only the requester or provider can raise it."""
    valid_reasons = {"damage", "incomplete", "fraud", "overcharge", "no_show", "theft", "other"}
    if data.reason not in valid_reasons:
        raise HTTPException(status_code=400, detail=f"Reason must be one of: {valid_reasons}")

    result = await db.execute(select(Task).where(Task.id == data.task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Only requester or provider can raise
    if current_user.id not in (task.requester_id, task.provider_id):
        raise HTTPException(status_code=403, detail="Only task requester or provider can raise a dispute")

    # Check no existing open dispute
    existing = await db.execute(
        select(Dispute).where(
            Dispute.task_id == data.task_id,
            Dispute.status.in_([DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW])
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A dispute is already open for this task")

    # Update task status to disputed
    task.status = TaskStatus.DISPUTED

    # If payment exists, mark escrow as disputed
    payment_result = await db.execute(select(Payment).where(Payment.task_id == data.task_id))
    payment = payment_result.scalar_one_or_none()
    if payment and payment.escrow_status == EscrowStatus.HELD:
        payment.escrow_status = EscrowStatus.DISPUTED

    dispute = Dispute(
        task_id=data.task_id,
        raised_by=current_user.id,
        reason=data.reason,
        description=data.description,
        evidence_urls=data.evidence_urls,
    )
    db.add(dispute)
    await db.flush()

    return {
        "id": str(dispute.id),
        "task_id": str(dispute.task_id),
        "status": "open",
        "message": "Dispute raised. Our team will review within 24-48 hours.",
    }


# ── My Disputes ───────────────────────────────────────────────

@router.get("/my")
async def get_my_disputes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all disputes raised by or involving the current user."""
    result = await db.execute(
        select(Dispute)
        .where(Dispute.raised_by == current_user.id)
        .order_by(Dispute.created_at.desc())
    )
    disputes = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "task_id": str(d.task_id),
            "reason": d.reason,
            "description": d.description,
            "status": d.status.value,
            "resolution_notes": d.resolution_notes,
            "created_at": d.created_at.isoformat(),
            "resolved_at": d.resolved_at.isoformat() if d.resolved_at else None,
        }
        for d in disputes
    ]


# ── Get Dispute Detail ────────────────────────────────────────

@router.get("/{dispute_id}")
async def get_dispute(
    dispute_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get dispute details."""
    result = await db.execute(select(Dispute).where(Dispute.id == dispute_id))
    dispute = result.scalar_one_or_none()

    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    # Check authorization
    task_result = await db.execute(select(Task).where(Task.id == dispute.task_id))
    task = task_result.scalar_one_or_none()

    if current_user.id not in (dispute.raised_by, task.requester_id, task.provider_id):
        if current_user.trust_score < 90:  # Not admin either
            raise HTTPException(status_code=403, detail="Not authorized")

    return {
        "id": str(dispute.id),
        "task_id": str(dispute.task_id),
        "raised_by": str(dispute.raised_by),
        "reason": dispute.reason,
        "description": dispute.description,
        "evidence_urls": dispute.evidence_urls,
        "status": dispute.status.value,
        "resolution_notes": dispute.resolution_notes,
        "created_at": dispute.created_at.isoformat(),
        "resolved_at": dispute.resolved_at.isoformat() if dispute.resolved_at else None,
    }


# ── Admin: List All Open Disputes ─────────────────────────────

@router.get("/admin/pending")
async def list_pending_disputes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: list all open disputes."""
    if current_user.trust_score < 90:
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(
        select(Dispute)
        .where(Dispute.status.in_([DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW]))
        .order_by(Dispute.created_at.asc())
    )
    disputes = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "task_id": str(d.task_id),
            "raised_by": str(d.raised_by),
            "reason": d.reason,
            "description": d.description,
            "evidence_urls": d.evidence_urls,
            "status": d.status.value,
            "created_at": d.created_at.isoformat(),
        }
        for d in disputes
    ]


# ── Admin: Resolve Dispute ────────────────────────────────────

@router.put("/admin/{dispute_id}/resolve")
async def resolve_dispute(
    dispute_id: str,
    data: ResolveDisputeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: resolve a dispute in favor of requester or provider."""
    if current_user.trust_score < 90:
        raise HTTPException(status_code=403, detail="Admin access required")

    if data.resolution not in ("requester", "provider"):
        raise HTTPException(status_code=400, detail="Resolution must be 'requester' or 'provider'")

    result = await db.execute(select(Dispute).where(Dispute.id == dispute_id))
    dispute = result.scalar_one_or_none()

    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    if dispute.status not in (DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW):
        raise HTTPException(status_code=400, detail="Dispute is already resolved")

    # Resolve dispute
    if data.resolution == "requester":
        dispute.status = DisputeStatus.RESOLVED_REQUESTER
    else:
        dispute.status = DisputeStatus.RESOLVED_PROVIDER

    dispute.resolution_notes = data.notes
    dispute.resolved_at = datetime.now(timezone.utc)

    # Handle payment based on resolution
    task_result = await db.execute(select(Task).where(Task.id == dispute.task_id))
    task = task_result.scalar_one_or_none()

    payment_result = await db.execute(select(Payment).where(Payment.task_id == dispute.task_id))
    payment = payment_result.scalar_one_or_none()

    if data.resolution == "requester":
        # Refund to requester
        if payment and payment.escrow_status == EscrowStatus.DISPUTED:
            payment.escrow_status = EscrowStatus.REFUNDED
        if task:
            task.status = TaskStatus.CANCELLED
        # Penalize provider
        if task and task.provider_id:
            provider_result = await db.execute(select(User).where(User.id == task.provider_id))
            provider = provider_result.scalar_one_or_none()
            if provider:
                provider.trust_score = max(0, provider.trust_score - 15)
    else:
        # Release to provider
        if payment and payment.escrow_status == EscrowStatus.DISPUTED:
            payment.escrow_status = EscrowStatus.RELEASED
            payment.released_at = datetime.now(timezone.utc)
        if task:
            task.status = TaskStatus.COMPLETED

    await db.flush()
    return {
        "message": f"Dispute resolved in favor of {data.resolution}",
        "status": dispute.status.value,
    }

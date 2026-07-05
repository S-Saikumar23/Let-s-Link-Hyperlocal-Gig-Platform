"""
Document verification routes — ID proofs and skill certificates.
Users upload documents → Admin reviews → Approved/Rejected → Trust badge.
"""
import os
import uuid
import shutil
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models import UserDocument, User, DocType, DocStatus
from auth import get_current_user

router = APIRouter(prefix="/documents", tags=["Documents"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "documents")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Upload Document ───────────────────────────────────────────

@router.post("/upload")
async def upload_document(
    doc_type: str = Form(...),
    title: str = Form(...),
    doc_number: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document (PAN, DL, Certificate, etc.) for verification."""
    # Validate doc type
    try:
        dtype = DocType(doc_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid doc_type. Must be one of: {[e.value for e in DocType]}"
        )

    # Validate file type
    allowed = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, WebP, or PDF allowed")

    # Limit file size (5MB)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    # Save file
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)

    file_url = f"/uploads/documents/{filename}"

    # Save to DB
    doc = UserDocument(
        user_id=current_user.id,
        doc_type=dtype,
        title=title,
        doc_number=doc_number,
        file_url=file_url,
        status=DocStatus.PENDING,
    )
    db.add(doc)
    await db.flush()

    return {
        "id": str(doc.id),
        "doc_type": doc.doc_type.value,
        "title": doc.title,
        "status": "pending",
        "message": "Document uploaded! It will be reviewed within 24-48 hours.",
    }


# ── My Documents ──────────────────────────────────────────────

@router.get("/my")
async def get_my_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all documents uploaded by the current user."""
    result = await db.execute(
        select(UserDocument)
        .where(UserDocument.user_id == current_user.id)
        .order_by(UserDocument.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "doc_type": d.doc_type.value,
            "title": d.title,
            "doc_number": d.doc_number,
            "file_url": d.file_url,
            "status": d.status.value,
            "admin_notes": d.admin_notes,
            "verified_at": d.verified_at.isoformat() if d.verified_at else None,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


# ── User's Public Documents (verified only) ──────────────────

@router.get("/user/{user_id}")
async def get_user_documents(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get verified documents for a user (public view)."""
    result = await db.execute(
        select(UserDocument)
        .where(UserDocument.user_id == user_id, UserDocument.status == DocStatus.APPROVED)
        .order_by(UserDocument.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "doc_type": d.doc_type.value,
            "title": d.title,
            "status": "verified",
            "verified_at": d.verified_at.isoformat() if d.verified_at else None,
        }
        for d in docs
    ]


# ── Admin: List Pending Documents ─────────────────────────────

@router.get("/admin/pending")
async def list_pending_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: list all documents awaiting review."""
    # Simple admin check — in production, use role-based access
    if current_user.trust_score < 90:
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(
        select(UserDocument)
        .where(UserDocument.status == DocStatus.PENDING)
        .order_by(UserDocument.created_at.asc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "user_id": str(d.user_id),
            "doc_type": d.doc_type.value,
            "title": d.title,
            "doc_number": d.doc_number,
            "file_url": d.file_url,
            "status": d.status.value,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


# ── Admin: Approve/Reject Document ────────────────────────────

class ReviewDocumentRequest(BaseModel):
    action: str  # "approve" or "reject"
    notes: Optional[str] = None


@router.put("/admin/{doc_id}/review")
async def review_document(
    doc_id: str,
    data: ReviewDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: approve or reject a document."""
    if current_user.trust_score < 90:
        raise HTTPException(status_code=403, detail="Admin access required")

    if data.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")

    result = await db.execute(select(UserDocument).where(UserDocument.id == doc_id))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if data.action == "approve":
        doc.status = DocStatus.APPROVED
        doc.verified_at = datetime.now(timezone.utc)
        doc.admin_notes = data.notes

        # Boost user trust score
        user_result = await db.execute(select(User).where(User.id == doc.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            if doc.doc_type in (DocType.PAN_CARD, DocType.DRIVING_LICENSE, DocType.VOTER_ID):
                user.trust_score = min(100, user.trust_score + 10)
                user.verification_level = "standard"
            elif doc.doc_type in (DocType.SKILL_CERTIFICATE, DocType.TRADE_LICENSE):
                user.trust_score = min(100, user.trust_score + 5)

    else:
        doc.status = DocStatus.REJECTED
        doc.admin_notes = data.notes or "Document could not be verified"

    await db.flush()
    return {"message": f"Document {data.action}d", "status": doc.status.value}


# ── Delete My Document ────────────────────────────────────────

@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document (user can only delete their own)."""
    result = await db.execute(select(UserDocument).where(UserDocument.id == doc_id))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your document")

    # Delete file
    filepath = os.path.join(os.path.dirname(__file__), "..", doc.file_url.lstrip("/"))
    if os.path.exists(filepath):
        os.remove(filepath)

    await db.delete(doc)
    await db.flush()
    return {"message": "Document deleted"}

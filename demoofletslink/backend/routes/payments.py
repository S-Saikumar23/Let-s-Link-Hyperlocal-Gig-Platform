import razorpay
import hmac
import hashlib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from database import get_db
from models import Payment, Task, User, TaskStatus, EscrowStatus
from auth import get_current_user
from config import settings

router = APIRouter(prefix="/payments", tags=["Payments"])

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)

PLATFORM_FEE_PERCENT = 10  # 10% platform commission


# ── Schemas ────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    task_id: str


class VerifyPaymentRequest(BaseModel):
    task_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class ReleasePaymentRequest(BaseModel):
    task_id: str


# ── Create Order ───────────────────────────────────────────────

@router.post("/create-order")
async def create_payment_order(
    data: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Razorpay order for a completed task. Falls back to demo mode if Razorpay keys are invalid."""
    import uuid as _uuid

    result = await db.execute(select(Task).where(Task.id == data.task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the task requester can pay")

    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Task must be completed before payment")

    if not task.provider_id:
        raise HTTPException(status_code=400, detail="No provider assigned to this task")

    # Check if payment already exists
    existing = await db.execute(select(Payment).where(Payment.task_id == data.task_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Payment already exists for this task")

    # Calculate amount (use agreed_price or budget_max)
    amount = task.agreed_price or task.budget_max or task.budget_min or 0
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid task amount")

    platform_fee = round(amount * PLATFORM_FEE_PERCENT / 100, 2)
    total_amount = amount  # Total charged to requester

    # Try Razorpay, fall back to demo mode if keys are invalid
    demo_mode = False
    order_id = None

    try:
        razorpay_order = razorpay_client.order.create({
            "amount": int(total_amount * 100),  # Convert to paise
            "currency": "INR",
            "receipt": f"task_{data.task_id[:8]}",
            "notes": {
                "task_id": str(data.task_id),
                "payer_id": str(current_user.id),
                "payee_id": str(task.provider_id),
            },
        })
        order_id = razorpay_order["id"]
    except Exception as e:
        # Razorpay keys are invalid — use demo mode
        print(f"[DEMO MODE] Razorpay unavailable ({e}), using demo payment")
        demo_mode = True
        order_id = f"demo_order_{_uuid.uuid4().hex[:16]}"

    # Save payment record
    payment = Payment(
        task_id=data.task_id,
        payer_id=current_user.id,
        payee_id=task.provider_id,
        amount=total_amount,
        platform_fee=platform_fee,
        razorpay_order_id=order_id,
    )
    db.add(payment)
    await db.flush()

    return {
        "order_id": order_id,
        "amount": total_amount,
        "currency": "INR",
        "platform_fee": platform_fee,
        "provider_receives": total_amount - platform_fee,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "demo_mode": demo_mode,
    }


# ── Verify Payment ────────────────────────────────────────────

@router.post("/verify")
async def verify_payment(
    data: VerifyPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify Razorpay payment signature and update payment record."""
    result = await db.execute(
        select(Payment).where(Payment.razorpay_order_id == data.razorpay_order_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment order not found")

    if payment.payer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Demo mode — skip signature verification
    if data.razorpay_order_id.startswith("demo_order_"):
        payment.razorpay_payment_id = data.razorpay_payment_id
        payment.razorpay_signature = "demo_signature"
        payment.escrow_status = EscrowStatus.HELD
        await db.flush()
        return {"message": "Demo payment verified and held in escrow", "status": "held"}

    # Verify Razorpay signature
    message = f"{data.razorpay_order_id}|{data.razorpay_payment_id}"
    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    if expected_signature != data.razorpay_signature:
        raise HTTPException(status_code=400, detail="Payment verification failed")

    # Update payment record
    payment.razorpay_payment_id = data.razorpay_payment_id
    payment.razorpay_signature = data.razorpay_signature
    payment.escrow_status = EscrowStatus.HELD
    await db.flush()

    return {"message": "Payment verified and held in escrow", "status": "held"}


# ── Release Payment ───────────────────────────────────────────

@router.post("/release")
async def release_payment(
    data: ReleasePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Release escrowed payment to the provider."""
    result = await db.execute(select(Payment).where(Payment.task_id == data.task_id))
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.payer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the payer can release funds")

    if payment.escrow_status != EscrowStatus.HELD:
        raise HTTPException(status_code=400, detail=f"Payment is {payment.escrow_status.value}, cannot release")

    payment.escrow_status = EscrowStatus.RELEASED
    payment.released_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "message": "Payment released to provider",
        "amount_released": payment.amount - payment.platform_fee,
        "platform_fee": payment.platform_fee,
    }


# ── Payment Status ────────────────────────────────────────────

@router.get("/status/{task_id}")
async def get_payment_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get payment status for a task."""
    result = await db.execute(select(Payment).where(Payment.task_id == task_id))
    payment = result.scalar_one_or_none()

    if not payment:
        return {"status": "no_payment", "message": "No payment found for this task"}

    if payment.payer_id != current_user.id and payment.payee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return {
        "status": payment.escrow_status.value,
        "amount": payment.amount,
        "platform_fee": payment.platform_fee,
        "provider_receives": payment.amount - payment.platform_fee,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
        "released_at": payment.released_at.isoformat() if payment.released_at else None,
    }

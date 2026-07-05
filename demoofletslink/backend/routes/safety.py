import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from database import get_db
from models import User, Report, ReportStatus
from auth import get_current_user

router = APIRouter(prefix="/safety", tags=["Safety & Verification"])


# ── Schemas ────────────────────────────────────────────────────

class OTPRequest(BaseModel):
    phone: str


class OTPVerify(BaseModel):
    phone: str
    otp: str = Field(..., min_length=6, max_length=6)


class ReportCreate(BaseModel):
    reported_id: str
    reason: str = Field(..., min_length=2, max_length=50)
    description: str | None = None


class EmergencyContactUpdate(BaseModel):
    emergency_contact: str = Field(..., min_length=10, max_length=15)


# ── OTP Endpoints ──────────────────────────────────────────────

@router.post("/otp/send")
async def send_otp(data: OTPRequest, db: AsyncSession = Depends(get_db)):
    """Send OTP to phone number. In dev mode, OTP is logged to console."""
    result = await db.execute(select(User).where(User.phone == data.phone))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Phone number not registered")

    if user.is_phone_verified:
        return {"message": "Phone already verified", "verified": True}

    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    await db.flush()

    # DEV MODE: Log to console (replace with SMS API in production)
    print(f"\n{'='*50}")
    print(f"📱 OTP for {data.phone}: {otp}")
    print(f"{'='*50}\n")

    # TODO: In production, integrate SMS provider here:
    # - MSG91: requests.post("https://api.msg91.com/api/v5/otp", ...)
    # - Twilio: client.messages.create(to=phone, body=f"Your OTP is {otp}")

    return {"message": "OTP sent successfully", "dev_otp": otp}


@router.post("/otp/verify")
async def verify_otp(data: OTPVerify, db: AsyncSession = Depends(get_db)):
    """Verify the OTP code."""
    result = await db.execute(select(User).where(User.phone == data.phone))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Phone number not registered")

    if user.is_phone_verified:
        return {"message": "Phone already verified", "verified": True}

    if not user.otp_code or not user.otp_expires_at:
        raise HTTPException(status_code=400, detail="No OTP requested. Send OTP first.")

    if datetime.now(timezone.utc) > user.otp_expires_at:
        user.otp_code = None
        user.otp_expires_at = None
        await db.flush()
        raise HTTPException(status_code=400, detail="OTP expired. Request a new one.")

    if user.otp_code != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Mark as verified
    user.is_phone_verified = True
    user.otp_code = None
    user.otp_expires_at = None
    if user.trust_score < 60:
        user.trust_score = 60  # Boost trust score on verification
    await db.flush()

    return {"message": "Phone verified successfully!", "verified": True}


# ── Report Endpoints ───────────────────────────────────────────

@router.post("/reports", status_code=status.HTTP_201_CREATED)
async def create_report(
    data: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Report a user for policy violations."""
    if str(current_user.id) == data.reported_id:
        raise HTTPException(status_code=400, detail="Cannot report yourself")

    # Check reported user exists
    result = await db.execute(select(User).where(User.id == data.reported_id))
    reported_user = result.scalar_one_or_none()
    if not reported_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check for duplicate report
    existing = await db.execute(
        select(Report).where(
            Report.reporter_id == current_user.id,
            Report.reported_id == data.reported_id,
            Report.status == ReportStatus.PENDING,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You already have a pending report for this user")

    report = Report(
        reporter_id=current_user.id,
        reported_id=data.reported_id,
        reason=data.reason,
        description=data.description,
    )
    db.add(report)

    # Auto-decrease trust score on multiple reports
    report_count_result = await db.execute(
        select(Report).where(Report.reported_id == data.reported_id)
    )
    report_count = len(report_count_result.scalars().all())
    if report_count >= 3 and reported_user.trust_score > 20:
        reported_user.trust_score = max(20, reported_user.trust_score - 10)

    await db.flush()

    return {"message": "Report submitted. We'll review it shortly.", "report_id": str(report.id)}


# ── Emergency Contact ──────────────────────────────────────────

@router.put("/emergency-contact")
async def update_emergency_contact(
    data: EmergencyContactUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set or update emergency contact number."""
    current_user.emergency_contact = data.emergency_contact
    await db.flush()
    return {"message": "Emergency contact updated", "emergency_contact": data.emergency_contact}


@router.post("/sos")
async def trigger_sos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger SOS alert. Logs alert and returns emergency info."""
    print(f"\n{'!'*50}")
    print(f"🆘 SOS ALERT from {current_user.name} ({current_user.phone})")
    print(f"   Location: {current_user.latitude}, {current_user.longitude}")
    print(f"   Emergency contact: {current_user.emergency_contact or 'Not set'}")
    print(f"{'!'*50}\n")

    # TODO: In production, send SMS/call to emergency contact + alert admins

    return {
        "message": "SOS alert triggered! Help is on the way.",
        "emergency_contact": current_user.emergency_contact,
        "user_location": {
            "latitude": current_user.latitude,
            "longitude": current_user.longitude,
        },
    }

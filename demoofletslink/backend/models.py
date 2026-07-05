import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime,
    ForeignKey, Enum as SQLEnum, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
import enum


# ── Enums ──────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    REQUESTER = "requester"
    PROVIDER = "provider"
    BOTH = "both"


class VerificationLevel(str, enum.Enum):
    BASIC = "basic"
    STANDARD = "standard"
    ENHANCED = "enhanced"


class TaskUrgency(str, enum.Enum):
    NOW = "now"
    TODAY = "today"
    THIS_WEEK = "this_week"
    FLEXIBLE = "flexible"


class TaskStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


class OfferStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class PaymentMethod(str, enum.Enum):
    UPI = "upi"
    CARD = "card"
    WALLET = "wallet"
    CASH = "cash"


class EscrowStatus(str, enum.Enum):
    HELD = "held"
    RELEASED = "released"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    QUICK_REPLY = "quick_reply"
    LOCATION = "location"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


# ── Models ─────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(15), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    avatar_url = Column(Text, nullable=True)
    role = Column(SQLEnum(UserRole), default=UserRole.BOTH, nullable=False)
    trust_score = Column(Integer, default=50)
    verification_level = Column(SQLEnum(VerificationLevel), default=VerificationLevel.BASIC)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(Text, nullable=True)
    is_online = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    # OTP & Verification
    is_phone_verified = Column(Boolean, default=False)
    otp_code = Column(String(6), nullable=True)
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    # Safety
    emergency_contact = Column(String(15), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    skills = relationship("ProviderSkill", back_populates="user", cascade="all, delete-orphan")
    posted_tasks = relationship("Task", back_populates="requester", foreign_keys="Task.requester_id")
    accepted_tasks = relationship("Task", back_populates="provider", foreign_keys="Task.provider_id")
    offers = relationship("TaskOffer", back_populates="provider")
    reviews_given = relationship("Review", back_populates="reviewer", foreign_keys="Review.reviewer_id")
    reviews_received = relationship("Review", back_populates="reviewee", foreign_keys="Review.reviewee_id")


class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    icon = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    skills = relationship("ProviderSkill", back_populates="category")
    tasks = relationship("Task", back_populates="category")


class ProviderSkill(Base):
    __tablename__ = "provider_skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    experience_years = Column(Integer, default=0)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="skills")
    category = relationship("Category", back_populates="skills")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requester_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    budget_min = Column(Float, nullable=True)
    budget_max = Column(Float, nullable=True)
    agreed_price = Column(Float, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(Text, nullable=True)
    urgency = Column(SQLEnum(TaskUrgency), default=TaskUrgency.FLEXIBLE)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.OPEN, index=True)
    visibility_radius_km = Column(Integer, default=5)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    requester = relationship("User", back_populates="posted_tasks", foreign_keys=[requester_id])
    provider = relationship("User", back_populates="accepted_tasks", foreign_keys=[provider_id])
    category = relationship("Category", back_populates="tasks")
    offers = relationship("TaskOffer", back_populates="task", cascade="all, delete-orphan")
    media = relationship("TaskMedia", back_populates="task", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="task", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="task", cascade="all, delete-orphan")
    payment = relationship("Payment", back_populates="task", uselist=False)


class TaskMedia(Base):
    __tablename__ = "task_media"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    url = Column(Text, nullable=False)
    media_type = Column(String(10), default="image")  # image or video
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    task = relationship("Task", back_populates="media")


class TaskOffer(Base):
    __tablename__ = "task_offers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    offered_price = Column(Float, nullable=False)
    message = Column(Text, nullable=True)
    status = Column(SQLEnum(OfferStatus), default=OfferStatus.PENDING)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    task = relationship("Task", back_populates="offers")
    provider = relationship("User", back_populates="offers")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), unique=True, nullable=False)
    payer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    payee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    platform_fee = Column(Float, default=0.0)
    tip = Column(Float, default=0.0)
    payment_method = Column(SQLEnum(PaymentMethod), default=PaymentMethod.UPI)
    escrow_status = Column(SQLEnum(EscrowStatus), default=EscrowStatus.HELD)
    razorpay_order_id = Column(String(100), nullable=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    razorpay_signature = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    released_at = Column(DateTime(timezone=True), nullable=True)

    task = relationship("Task", back_populates="payment")
    payer = relationship("User", foreign_keys=[payer_id])
    payee = relationship("User", foreign_keys=[payee_id])


class Review(Base):
    __tablename__ = "reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reviewee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="valid_rating"),
    )

    task = relationship("Task", back_populates="reviews")
    reviewer = relationship("User", back_populates="reviews_given", foreign_keys=[reviewer_id])
    reviewee = relationship("User", back_populates="reviews_received", foreign_keys=[reviewee_id])


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(SQLEnum(MessageType), default=MessageType.TEXT)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    task = relationship("Task", back_populates="messages")
    sender = relationship("User")


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reported_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason = Column(String(50), nullable=False)  # harassment, fraud, spam, inappropriate, other
    description = Column(Text, nullable=True)
    status = Column(SQLEnum(ReportStatus), default=ReportStatus.PENDING)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reporter = relationship("User", foreign_keys=[reporter_id])
    reported = relationship("User", foreign_keys=[reported_id])


class DocType(str, enum.Enum):
    PAN_CARD = "pan_card"
    DRIVING_LICENSE = "driving_license"
    VOTER_ID = "voter_id"
    SKILL_CERTIFICATE = "skill_certificate"
    TRADE_LICENSE = "trade_license"
    OTHER = "other"


class DocStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DisputeStatus(str, enum.Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED_REQUESTER = "resolved_requester"   # Decided in requester's favor
    RESOLVED_PROVIDER = "resolved_provider"     # Decided in provider's favor
    CLOSED = "closed"


class UserDocument(Base):
    """ID documents and skill certificates uploaded by users."""
    __tablename__ = "user_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    doc_type = Column(SQLEnum(DocType), nullable=False)
    title = Column(String(200), nullable=False)           # "PAN Card", "ITI Electrician Certificate"
    doc_number = Column(String(50), nullable=True)        # PAN number, DL number (optional)
    file_url = Column(Text, nullable=False)               # Uploaded image URL
    status = Column(SQLEnum(DocStatus), default=DocStatus.PENDING)
    admin_notes = Column(Text, nullable=True)             # Reason for rejection
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User")


class TaskProof(Base):
    """Before/after photo proof for task completion."""
    __tablename__ = "task_proofs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    proof_type = Column(String(20), nullable=False)       # "before", "after", "delivery"
    file_url = Column(Text, nullable=False)
    caption = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    task = relationship("Task")
    uploader = relationship("User")


class Dispute(Base):
    """Dispute resolution between requester and provider."""
    __tablename__ = "disputes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    raised_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason = Column(String(50), nullable=False)           # damage, incomplete, fraud, overcharge, other
    description = Column(Text, nullable=False)
    evidence_urls = Column(Text, nullable=True)           # Comma-separated image URLs
    status = Column(SQLEnum(DisputeStatus), default=DisputeStatus.OPEN)
    resolution_notes = Column(Text, nullable=True)        # Admin's resolution explanation
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    task = relationship("Task")
    raiser = relationship("User")

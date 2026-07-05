from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID
from models import UserRole, TaskUrgency, TaskStatus, OfferStatus, PaymentMethod, MessageType


# ── Auth Schemas ───────────────────────────────────────────────

class UserRegister(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)
    name: str = Field(..., min_length=2, max_length=100)
    email: str
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.BOTH
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


# ── User Schemas ───────────────────────────────────────────────

class SkillCreate(BaseModel):
    category_id: UUID
    experience_years: int = 0


class SkillResponse(BaseModel):
    id: UUID
    category_id: UUID
    category_name: Optional[str] = None
    experience_years: int
    verified: bool

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: UUID
    phone: str
    name: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    role: UserRole
    trust_score: int
    verification_level: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    is_online: bool
    is_phone_verified: bool = False
    emergency_contact: Optional[str] = None
    created_at: datetime
    skills: List[SkillResponse] = []

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[UserRole] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    is_online: Optional[bool] = None


class UserPublicProfile(BaseModel):
    id: UUID
    name: str
    avatar_url: Optional[str] = None
    role: UserRole
    trust_score: int
    verification_level: str
    is_online: bool
    created_at: datetime
    skills: List[SkillResponse] = []
    avg_rating: Optional[float] = None
    tasks_completed: int = 0

    class Config:
        from_attributes = True


# ── Category Schemas ───────────────────────────────────────────

class CategoryResponse(BaseModel):
    id: UUID
    name: str
    icon: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


# ── Task Schemas ───────────────────────────────────────────────

class TaskCreate(BaseModel):
    category_id: UUID
    title: str = Field(..., min_length=5, max_length=200)
    description: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    latitude: float
    longitude: float
    address: Optional[str] = None
    urgency: TaskUrgency = TaskUrgency.FLEXIBLE
    visibility_radius_km: int = 5


class TaskResponse(BaseModel):
    id: UUID
    requester_id: UUID
    requester: Optional[UserResponse] = None
    provider_id: Optional[UUID] = None
    provider: Optional[UserResponse] = None
    category_id: UUID
    category: Optional[CategoryResponse] = None
    title: str
    description: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    agreed_price: Optional[float] = None
    latitude: float
    longitude: float
    address: Optional[str] = None
    urgency: TaskUrgency
    status: TaskStatus
    visibility_radius_km: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    offers_count: int = 0

    class Config:
        from_attributes = True


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    urgency: Optional[TaskUrgency] = None
    status: Optional[TaskStatus] = None


# ── Offer Schemas ──────────────────────────────────────────────

class OfferCreate(BaseModel):
    task_id: UUID
    offered_price: float
    message: Optional[str] = None


class OfferResponse(BaseModel):
    id: UUID
    task_id: UUID
    provider_id: UUID
    provider: Optional[UserResponse] = None
    offered_price: float
    message: Optional[str] = None
    status: OfferStatus
    created_at: datetime

    class Config:
        from_attributes = True


# ── Review Schemas ─────────────────────────────────────────────

class ReviewCreate(BaseModel):
    task_id: UUID
    reviewee_id: UUID
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class ReviewResponse(BaseModel):
    id: UUID
    task_id: UUID
    reviewer_id: UUID
    reviewer: Optional[UserResponse] = None
    reviewee_id: UUID
    rating: int
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Chat Schemas ───────────────────────────────────────────────

class MessageCreate(BaseModel):
    task_id: UUID
    content: str
    message_type: MessageType = MessageType.TEXT


class MessageResponse(BaseModel):
    id: UUID
    task_id: UUID
    sender_id: UUID
    sender_name: Optional[str] = None
    content: str
    message_type: MessageType
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Payment Schemas ────────────────────────────────────────────

class PaymentResponse(BaseModel):
    id: UUID
    task_id: UUID
    amount: float
    platform_fee: float
    tip: float
    payment_method: PaymentMethod
    escrow_status: str
    created_at: datetime

    class Config:
        from_attributes = True

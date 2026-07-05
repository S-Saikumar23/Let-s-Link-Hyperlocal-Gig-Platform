from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from typing import Optional, List
from database import get_db
from models import Task, TaskOffer, User, Category, TaskStatus, OfferStatus
from schemas import (
    TaskCreate, TaskResponse, TaskUpdate,
    OfferCreate, OfferResponse, CategoryResponse
)
from auth import get_current_user
import math

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in kilometers."""
    R = 6371  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c


# ── Categories ─────────────────────────────────────────────────

@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    """Get all task categories."""
    result = await db.execute(select(Category).where(Category.is_active == True))
    categories = result.scalars().all()
    return [CategoryResponse.model_validate(c) for c in categories]


# ── Task CRUD ──────────────────────────────────────────────────

@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new task request."""
    # Verify category exists
    result = await db.execute(select(Category).where(Category.id == data.category_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Category not found")

    task = Task(
        requester_id=current_user.id,
        category_id=data.category_id,
        title=data.title,
        description=data.description,
        budget_min=data.budget_min,
        budget_max=data.budget_max,
        latitude=data.latitude,
        longitude=data.longitude,
        address=data.address,
        urgency=data.urgency,
        visibility_radius_km=data.visibility_radius_km,
    )
    db.add(task)
    await db.flush()

    # Re-query with eager loading to avoid MissingGreenlet in async context
    result = await db.execute(
        select(Task).options(
            selectinload(Task.requester).selectinload(User.skills),
            selectinload(Task.category),
        ).where(Task.id == task.id)
    )
    task = result.scalar_one()

    return TaskResponse.model_validate(task)


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    category_id: Optional[str] = None,
    search: Optional[str] = Query(None, min_length=1, max_length=100),
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: int = 10,
    limit: int = Query(20, le=50),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List tasks with optional filters. Supports search and proximity filtering."""
    query = select(Task).options(
        selectinload(Task.requester).selectinload(User.skills),
        selectinload(Task.category)
    )

    if status_filter:
        query = query.where(Task.status == status_filter)
    else:
        query = query.where(Task.status == TaskStatus.OPEN)

    if category_id:
        query = query.where(Task.category_id == category_id)

    if search:
        query = query.where(Task.title.ilike(f"%{search}%"))

    query = query.order_by(Task.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    tasks = result.scalars().all()

    # Apply proximity filter in Python (for MVP; use PostGIS in production)
    if latitude is not None and longitude is not None:
        filtered = []
        for task in tasks:
            dist = haversine_distance(latitude, longitude, task.latitude, task.longitude)
            if dist <= radius_km:
                filtered.append(task)
        tasks = filtered

    task_responses = []
    for task in tasks:
        resp = TaskResponse.model_validate(task)
        # Count offers
        offer_count = await db.execute(
            select(func.count(TaskOffer.id)).where(TaskOffer.task_id == task.id)
        )
        resp.offers_count = offer_count.scalar() or 0
        task_responses.append(resp)

    return task_responses


@router.get("/my-tasks", response_model=List[TaskResponse])
async def get_my_tasks(
    role: str = Query("requester", pattern="^(requester|provider)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get tasks posted by or assigned to the current user."""
    if role == "requester":
        query = select(Task).where(Task.requester_id == current_user.id)
    else:
        query = select(Task).where(Task.provider_id == current_user.id)

    query = query.options(
        selectinload(Task.requester).selectinload(User.skills),
        selectinload(Task.category)
    ).order_by(Task.created_at.desc())

    result = await db.execute(query)
    tasks = result.scalars().all()
    return [TaskResponse.model_validate(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific task by ID."""
    result = await db.execute(
        select(Task).options(
            selectinload(Task.requester).selectinload(User.skills),
            selectinload(Task.provider).selectinload(User.skills),
            selectinload(Task.category)
        ).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    resp = TaskResponse.model_validate(task)
    offer_count = await db.execute(
        select(func.count(TaskOffer.id)).where(TaskOffer.task_id == task.id)
    )
    resp.offers_count = offer_count.scalar() or 0

    return resp


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    data: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a task (only by requester)."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    await db.flush()

    # Re-query with eager loading to avoid MissingGreenlet in async context
    result = await db.execute(
        select(Task).options(
            selectinload(Task.requester).selectinload(User.skills),
            selectinload(Task.provider).selectinload(User.skills),
            selectinload(Task.category),
        ).where(Task.id == task_id)
    )
    task = result.scalar_one()
    return TaskResponse.model_validate(task)


# ── Offers ─────────────────────────────────────────────────────

@router.post("/{task_id}/offers", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(
    task_id: str,
    data: OfferCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit an offer/bid on a task."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.OPEN:
        raise HTTPException(status_code=400, detail="Task is no longer open")

    if task.requester_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot bid on your own task")

    # Check for existing offer
    existing = await db.execute(
        select(TaskOffer).where(
            TaskOffer.task_id == task_id,
            TaskOffer.provider_id == current_user.id,
            TaskOffer.status == OfferStatus.PENDING
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You already have a pending offer")

    offer = TaskOffer(
        task_id=task_id,
        provider_id=current_user.id,
        offered_price=data.offered_price,
        message=data.message,
    )
    db.add(offer)
    await db.flush()

    # Re-query with eager loading to avoid MissingGreenlet in async context
    result = await db.execute(
        select(TaskOffer).options(
            selectinload(TaskOffer.provider).selectinload(User.skills),
        ).where(TaskOffer.id == offer.id)
    )
    offer = result.scalar_one()

    return OfferResponse.model_validate(offer)


@router.get("/{task_id}/offers", response_model=List[OfferResponse])
async def get_task_offers(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all offers for a task (only accessible by task requester)."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(TaskOffer)
        .options(selectinload(TaskOffer.provider).selectinload(User.skills))
        .where(TaskOffer.task_id == task_id)
        .order_by(TaskOffer.created_at.desc())
    )
    offers = result.scalars().all()

    return [OfferResponse.model_validate(o) for o in offers]


@router.put("/{task_id}/offers/{offer_id}/accept", response_model=TaskResponse)
async def accept_offer(
    task_id: str,
    offer_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Accept an offer — assigns the provider and moves task to 'assigned'."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(select(TaskOffer).where(TaskOffer.id == offer_id))
    offer = result.scalar_one_or_none()

    if not offer or offer.task_id != task.id:
        raise HTTPException(status_code=404, detail="Offer not found")

    # Accept the offer
    offer.status = OfferStatus.ACCEPTED
    task.provider_id = offer.provider_id
    task.agreed_price = offer.offered_price
    task.status = TaskStatus.ASSIGNED

    # Reject all other pending offers
    other_offers = await db.execute(
        select(TaskOffer).where(
            TaskOffer.task_id == task_id,
            TaskOffer.id != offer_id,
            TaskOffer.status == OfferStatus.PENDING
        )
    )
    for other in other_offers.scalars().all():
        other.status = OfferStatus.REJECTED

    await db.flush()

    # Re-query with eager loading to avoid MissingGreenlet in async context
    result = await db.execute(
        select(Task).options(
            selectinload(Task.requester).selectinload(User.skills),
            selectinload(Task.provider).selectinload(User.skills),
            selectinload(Task.category),
        ).where(Task.id == task_id)
    )
    task = result.scalar_one()

    return TaskResponse.model_validate(task)


@router.put("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a task as completed (by requester)."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if task.status not in [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]:
        raise HTTPException(status_code=400, detail="Task cannot be completed in current state")

    from datetime import datetime, timezone
    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now(timezone.utc)

    await db.flush()

    # Re-query with eager loading to avoid MissingGreenlet in async context
    result = await db.execute(
        select(Task).options(
            selectinload(Task.requester).selectinload(User.skills),
            selectinload(Task.provider).selectinload(User.skills),
            selectinload(Task.category),
        ).where(Task.id == task_id)
    )
    task = result.scalar_one()

    return TaskResponse.model_validate(task)


@router.put("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel a task (by requester). Only works if task is open or assigned."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.requester_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if task.status not in [TaskStatus.OPEN, TaskStatus.ASSIGNED]:
        raise HTTPException(status_code=400, detail="Task cannot be cancelled in current state")

    # Cancel the task
    task.status = TaskStatus.CANCELLED

    # Reject all pending offers
    pending_offers = await db.execute(
        select(TaskOffer).where(
            TaskOffer.task_id == task_id,
            TaskOffer.status == OfferStatus.PENDING
        )
    )
    for offer in pending_offers.scalars().all():
        offer.status = OfferStatus.REJECTED

    await db.flush()

    # Re-query with eager loading to avoid MissingGreenlet in async context
    result = await db.execute(
        select(Task).options(
            selectinload(Task.requester).selectinload(User.skills),
            selectinload(Task.category),
        ).where(Task.id == task_id)
    )
    task = result.scalar_one()

    return TaskResponse.model_validate(task)

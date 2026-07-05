from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List
from database import get_db
from models import Review, Task, User, TaskStatus
from schemas import ReviewCreate, ReviewResponse
from auth import get_current_user

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("/", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit a review for a completed task."""
    # Verify task exists and is completed
    result = await db.execute(select(Task).where(Task.id == data.task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Can only review completed tasks")

    # Verify reviewer is part of the task
    if task.requester_id != current_user.id and task.provider_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Verify reviewee is the other party
    if data.reviewee_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot review yourself")

    if data.reviewee_id != task.requester_id and data.reviewee_id != task.provider_id:
        raise HTTPException(status_code=400, detail="Reviewee must be part of the task")

    # Check for existing review
    existing = await db.execute(
        select(Review).where(
            Review.task_id == data.task_id,
            Review.reviewer_id == current_user.id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You already reviewed this task")

    review = Review(
        task_id=data.task_id,
        reviewer_id=current_user.id,
        reviewee_id=data.reviewee_id,
        rating=data.rating,
        comment=data.comment,
    )
    db.add(review)
    await db.flush()

    # Re-query with eager loading to avoid MissingGreenlet in async context
    result = await db.execute(
        select(Review).options(
            selectinload(Review.reviewer).selectinload(User.skills),
        ).where(Review.id == review.id)
    )
    review = result.scalar_one()

    return ReviewResponse.model_validate(review)


@router.get("/user/{user_id}", response_model=List[ReviewResponse])
async def get_user_reviews(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all reviews for a specific user."""
    result = await db.execute(
        select(Review)
        .options(selectinload(Review.reviewer))
        .where(Review.reviewee_id == user_id)
        .order_by(Review.created_at.desc())
    )
    reviews = result.scalars().all()
    return [ReviewResponse.model_validate(r) for r in reviews]


@router.get("/user/{user_id}/summary")
async def get_review_summary(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get aggregated review statistics for a user."""
    result = await db.execute(
        select(
            func.count(Review.id),
            func.avg(Review.rating),
            func.min(Review.rating),
            func.max(Review.rating)
        ).where(Review.reviewee_id == user_id)
    )
    count, avg, min_r, max_r = result.one()

    # Rating distribution
    distribution = {}
    for star in range(1, 6):
        star_result = await db.execute(
            select(func.count(Review.id))
            .where(Review.reviewee_id == user_id, Review.rating == star)
        )
        distribution[str(star)] = star_result.scalar() or 0

    return {
        "total_reviews": count or 0,
        "average_rating": round(float(avg), 1) if avg else 0,
        "min_rating": min_r,
        "max_rating": max_r,
        "distribution": distribution
    }

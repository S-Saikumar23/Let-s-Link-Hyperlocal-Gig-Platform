from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from database import get_db
from models import User, ProviderSkill, Category, Review
from schemas import (
    UserResponse, UserUpdate, UserPublicProfile, SkillCreate, SkillResponse
)
from auth import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Get the current user's profile."""
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update the current user's profile."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.flush()

    # Re-query with eager loading to avoid MissingGreenlet in async context
    result = await db.execute(
        select(User).options(selectinload(User.skills)).where(User.id == current_user.id)
    )
    user = result.scalar_one()
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserPublicProfile)
async def get_user_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a user's public profile."""
    result = await db.execute(
        select(User).options(selectinload(User.skills)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Calculate average rating
    rating_result = await db.execute(
        select(func.avg(Review.rating), func.count(Review.id))
        .where(Review.reviewee_id == user_id)
    )
    avg_rating, review_count = rating_result.one()

    # Count completed tasks
    from models import Task, TaskStatus
    task_count_result = await db.execute(
        select(func.count(Task.id))
        .where(Task.provider_id == user_id, Task.status == TaskStatus.COMPLETED)
    )
    tasks_completed = task_count_result.scalar() or 0

    profile = UserPublicProfile.model_validate(user)
    profile.avg_rating = round(float(avg_rating), 1) if avg_rating else None
    profile.tasks_completed = tasks_completed

    return profile


@router.post("/me/skills", response_model=SkillResponse)
async def add_skill(
    data: SkillCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a skill to the current user's profile."""
    # Verify category exists
    result = await db.execute(select(Category).where(Category.id == data.category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Check for duplicate
    result = await db.execute(
        select(ProviderSkill)
        .where(
            ProviderSkill.user_id == current_user.id,
            ProviderSkill.category_id == data.category_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Skill already added")

    skill = ProviderSkill(
        user_id=current_user.id,
        category_id=data.category_id,
        experience_years=data.experience_years,
    )
    db.add(skill)
    await db.flush()
    await db.refresh(skill)

    resp = SkillResponse.model_validate(skill)
    resp.category_name = category.name
    return resp


@router.delete("/me/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove a skill from the current user's profile."""
    result = await db.execute(
        select(ProviderSkill)
        .where(ProviderSkill.id == skill_id, ProviderSkill.user_id == current_user.id)
    )
    skill = result.scalar_one_or_none()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    await db.delete(skill)

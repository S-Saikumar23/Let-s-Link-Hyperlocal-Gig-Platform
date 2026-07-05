from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import get_db
from models import User
from schemas import UserRegister, UserLogin, Token, UserResponse
from auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    # Check if phone already exists
    result = await db.execute(select(User).where(User.phone == data.phone))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )

    # Check if email already exists
    if data.email:
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    # Create user
    user = User(
        phone=data.phone,
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
        latitude=data.latitude,
        longitude=data.longitude,
        address=data.address,
    )
    db.add(user)
    await db.flush()

    # Re-query with eager loading to avoid async lazy-load errors
    result = await db.execute(
        select(User).options(selectinload(User.skills)).where(User.id == user.id)
    )
    user = result.scalar_one()

    # Generate token
    token = create_access_token(data={"sub": str(user.id)})

    return Token(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login with email and password."""
    result = await db.execute(
        select(User).options(selectinload(User.skills)).where(User.email == data.email)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    token = create_access_token(data={"sub": str(user.id)})

    return Token(
        access_token=token,
        user=UserResponse.model_validate(user)
    )

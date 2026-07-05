"""Run this to see the ACTUAL error when registering."""
import asyncio
import traceback
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

async def test_register():
    from database import async_session, init_db
    from models import User
    from schemas import UserRegister, UserResponse, Token
    from auth import hash_password, create_access_token
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    import uuid

    # Init DB
    await init_db()

    async with async_session() as db:
        try:
            phone = "0000000001"
            email = "debugtest@test.com"
            password = "testpass123"
            name = "Debug User"
            role = "both"

            # Check phone
            result = await db.execute(select(User).where(User.phone == phone))
            if result.scalar_one_or_none():
                print("[SKIP] Phone already exists — deleting and retrying")
                await db.execute(User.__table__.delete().where(User.phone == phone))
                await db.commit()

            # Check email
            result = await db.execute(select(User).where(User.email == email))
            if result.scalar_one_or_none():
                await db.execute(User.__table__.delete().where(User.email == email))
                await db.commit()

            from models import UserRole
            user = User(
                phone=phone,
                name=name,
                email=email,
                password_hash=hash_password(password),
                role=UserRole.BOTH,
                latitude=None,
                longitude=None,
                address=None,
            )
            db.add(user)
            await db.flush()
            print(f"[OK] User flushed: {user.id}")

            # Re-query with eager loading
            result = await db.execute(
                select(User).options(selectinload(User.skills)).where(User.id == user.id)
            )
            user = result.scalar_one()
            print(f"[OK] User re-queried: {user.id}")

            # Generate token
            token = create_access_token(data={"sub": str(user.id)})
            print(f"[OK] Token created")

            # Serialize
            user_resp = UserResponse.model_validate(user)
            print(f"[OK] UserResponse: {user_resp.model_dump()}")

            token_resp = Token(access_token=token, user=user_resp)
            print(f"[OK] Token response created")
            print("\n✅ REGISTRATION WORKS!")

        except Exception as e:
            print(f"\n❌ ERROR: {type(e).__name__}: {e}")
            print("\nFull traceback:")
            traceback.print_exc()

asyncio.run(test_register())

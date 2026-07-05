"""
Fix database schema: add missing columns that exist in models but not in the database.
Run from the backend directory:  python fix_db.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://postgres:sai123@localhost:5432/letslink"

MIGRATIONS = [
    ("users", "is_phone_verified", "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_phone_verified BOOLEAN DEFAULT FALSE"),
    ("users", "otp_code",          "ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_code VARCHAR(6)"),
    ("users", "otp_expires_at",    "ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_expires_at TIMESTAMPTZ"),
    ("users", "emergency_contact", "ALTER TABLE users ADD COLUMN IF NOT EXISTS emergency_contact VARCHAR(15)"),
    ("users", "updated_at",        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"),
]

async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        for table, col, sql in MIGRATIONS:
            try:
                await conn.execute(text(sql))
                print(f"[OK] {table}.{col} — added or already exists")
            except Exception as e:
                print(f"[WARN] {table}.{col} — {e}")
    await engine.dispose()
    print("\n[DONE] Database schema is up to date.")

if __name__ == "__main__":
    asyncio.run(main())

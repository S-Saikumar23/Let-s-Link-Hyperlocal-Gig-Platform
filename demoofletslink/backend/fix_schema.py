"""Fix database schema — add missing columns to existing tables without data loss."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def fix_schema():
    engine = create_async_engine("postgresql+asyncpg://postgres:sai123@localhost:5432/letslink")

    # List of ALTER TABLE statements to add missing columns safely
    migrations = [
        # Users table — missing columns
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_phone_verified BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_code VARCHAR(6)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_expires_at TIMESTAMPTZ",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS emergency_contact VARCHAR(15)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
    ]

    async with engine.begin() as conn:
        for sql in migrations:
            try:
                await conn.execute(text(sql))
                print(f"  [OK] {sql.split('ADD COLUMN IF NOT EXISTS ')[-1].split()[0] if 'ADD COLUMN' in sql else sql[:60]}")
            except Exception as e:
                print(f"  [SKIP] {sql[:60]}... — {e}")

    # Now check which tables exist and which are missing
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))
        existing_tables = {row[0] for row in result.fetchall()}
        print(f"\n  Existing tables: {sorted(existing_tables)}")

    # Create any missing tables (like user_documents, task_proofs, disputes)
    from database import Base
    from models import *  # noqa — register all models

    expected_tables = set(Base.metadata.tables.keys())
    missing_tables = expected_tables - existing_tables
    if missing_tables:
        print(f"  Missing tables: {sorted(missing_tables)}")
        # Create only the missing tables
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[Base.metadata.tables[t] for t in missing_tables]
            )
        print(f"  [OK] Created missing tables: {sorted(missing_tables)}")
    else:
        print("  [OK] All tables exist")

    # Verify users table columns
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='users' ORDER BY ordinal_position"
        ))
        cols = [row[0] for row in result.fetchall()]
        print(f"\n  Users columns: {cols}")

    await engine.dispose()
    print("\n✅ Schema fix complete!")


if __name__ == "__main__":
    asyncio.run(fix_schema())

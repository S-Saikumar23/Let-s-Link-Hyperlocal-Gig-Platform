"""Reset database — drop all tables and recreate from models."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from database import Base
from models import *  # noqa — import all models so Base.metadata knows about them

async def reset():
    engine = create_async_engine("postgresql+asyncpg://postgres:sai123@localhost:5432/letslink")
    async with engine.begin() as conn:
        print("Dropping all tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Creating all tables from models...")
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("✅ Database reset complete! All tables recreated.")

if __name__ == "__main__":
    asyncio.run(reset())

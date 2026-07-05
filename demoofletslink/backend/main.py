import uuid
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from config import settings
from database import init_db, async_session
from models import Category
from sqlalchemy import select

# Initialize Sentry for error tracking
import sentry_sdk
if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.2)
    print("[OK] Sentry error tracking enabled")

from routes.auth import router as auth_router
from routes.tasks import router as tasks_router
from routes.users import router as users_router
from routes.chat import router as chat_router
from routes.reviews import router as reviews_router
from routes.uploads import router as uploads_router
from routes.safety import router as safety_router
from routes.payments import router as payments_router
from routes.documents import router as documents_router
from routes.disputes import router as disputes_router
from routes.proofs import router as proofs_router


async def seed_categories(session):
    """Seed default task categories if they don't exist."""
    categories = [
        {"name": "Electrical", "icon": "zap", "description": "Electrical repairs, wiring, fan/light installation"},
        {"name": "Plumbing", "icon": "droplets", "description": "Pipe repair, tap fixing, bathroom issues"},
        {"name": "Cleaning", "icon": "sparkles", "description": "House cleaning, deep cleaning, post-event cleanup"},
        {"name": "Delivery", "icon": "package", "description": "Pick up and deliver items from shops"},
        {"name": "Moving", "icon": "truck", "description": "Help with furniture, packing, small moves"},
        {"name": "Painting", "icon": "paintbrush", "description": "Wall painting, touch-ups, home renovation"},
        {"name": "Carpentry", "icon": "hammer", "description": "Furniture repair, assembly, woodwork"},
        {"name": "Tutoring", "icon": "book-open", "description": "Academic help, language lessons, skill training"},
        {"name": "Cooking", "icon": "chef-hat", "description": "Meal preparation, event cooking, catering"},
        {"name": "Pet Care", "icon": "paw-print", "description": "Dog walking, pet sitting, grooming"},
        {"name": "Gardening", "icon": "flower-2", "description": "Lawn care, plant maintenance, landscaping"},
        {"name": "Tech Help", "icon": "monitor", "description": "Computer/phone repair, software setup, networking"},
        {"name": "Event Help", "icon": "party-popper", "description": "Setup, teardown, serving, decoration"},
        {"name": "Other", "icon": "more-horizontal", "description": "Any other task or service"},
    ]

    result = await session.execute(select(Category).limit(1))
    if result.scalar_one_or_none() is None:
        for cat_data in categories:
            cat = Category(id=uuid.uuid4(), **cat_data)
            session.add(cat)
        await session.commit()
        print("[OK] Seeded default categories")
    else:
        print("[INFO] Categories already exist, skipping seed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("[START] Starting Let's Link API...")
    await init_db()
    print("[OK] Database tables created")

    async with async_session() as session:
        await seed_categories(session)

    yield
    print("[STOP] Shutting down Let's Link API...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Hyperlocal gig-economy platform connecting service requesters with providers",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(auth_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(reviews_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")
app.include_router(safety_router, prefix="/api")
app.include_router(payments_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(disputes_router, prefix="/api")
app.include_router(proofs_router, prefix="/api")


# Health check
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


# Serve uploaded files
uploads_dir = os.path.join(os.path.dirname(__file__), settings.UPLOAD_DIR)
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Serve frontend static files
try:
    app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
except Exception:
    print("[WARN] Frontend directory not found, serving API only")

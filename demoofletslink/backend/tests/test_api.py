"""
Let's Link — API Test Suite

Run with: pytest backend/tests/ -v
"""
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import event

# We need to set up test database before importing app
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import app
from database import Base, get_db


# ── Test Config ────────────────────────────────────────────────

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:sai123@localhost:5432/letslink_test"
)

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    """Create all tables before tests, drop them after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    """Async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Shared State ───────────────────────────────────────────────

test_state = {
    "user1_token": None,
    "user1_id": None,
    "user2_token": None,
    "user2_id": None,
    "task_id": None,
    "offer_id": None,
    "category_id": None,
}


# ── Auth Tests ─────────────────────────────────────────────────

class TestAuth:
    @pytest.mark.asyncio
    async def test_register_user1(self, client):
        """Register first user."""
        res = await client.post("/api/auth/register", json={
            "phone": "9876543210",
            "name": "Test User 1",
            "email": "user1@test.com",
            "password": "test123",
            "role": "both",
        })
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        assert data["user"]["name"] == "Test User 1"
        test_state["user1_token"] = data["access_token"]
        test_state["user1_id"] = data["user"]["id"]

    @pytest.mark.asyncio
    async def test_register_user2(self, client):
        """Register second user."""
        res = await client.post("/api/auth/register", json={
            "phone": "9876543211",
            "name": "Test Provider",
            "email": "provider@test.com",
            "password": "test123",
            "role": "provider",
        })
        assert res.status_code == 201
        data = res.json()
        test_state["user2_token"] = data["access_token"]
        test_state["user2_id"] = data["user"]["id"]

    @pytest.mark.asyncio
    async def test_duplicate_register(self, client):
        """Duplicate phone should fail."""
        res = await client.post("/api/auth/register", json={
            "phone": "9876543210",
            "name": "Duplicate",
            "email": "user1@test.com",
            "password": "test123",
        })
        assert res.status_code in [400, 409]

    @pytest.mark.asyncio
    async def test_login(self, client):
        """Login with correct credentials."""
        res = await client.post("/api/auth/login", json={
            "email": "user1@test.com",
            "password": "test123",
        })
        assert res.status_code == 200
        assert "access_token" in res.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        """Login with wrong password should fail."""
        res = await client.post("/api/auth/login", json={
            "email": "user1@test.com",
            "password": "wrong",
        })
        assert res.status_code in [400, 401]


# ── Category Tests ─────────────────────────────────────────────

class TestCategories:
    @pytest.mark.asyncio
    async def test_list_categories(self, client):
        """List available categories."""
        res = await client.get("/api/tasks/categories")
        assert res.status_code == 200
        cats = res.json()
        assert isinstance(cats, list)
        if len(cats) > 0:
            test_state["category_id"] = cats[0]["id"]


# ── Task Tests ─────────────────────────────────────────────────

class TestTasks:
    @pytest.mark.asyncio
    async def test_create_task(self, client):
        """Create a new task."""
        cat_id = test_state.get("category_id")
        if not cat_id:
            pytest.skip("No category available")

        res = await client.post("/api/tasks/", json={
            "title": "Fix ceiling fan",
            "description": "Fan stopped working",
            "category_id": cat_id,
            "budget_min": 200,
            "budget_max": 500,
            "urgency": "today",
            "latitude": 12.97,
            "longitude": 77.59,
            "address": "Test Location",
        }, headers={"Authorization": f"Bearer {test_state['user1_token']}"})
        assert res.status_code == 201
        data = res.json()
        assert data["title"] == "Fix ceiling fan"
        assert data["status"] == "open"
        test_state["task_id"] = data["id"]

    @pytest.mark.asyncio
    async def test_list_tasks(self, client):
        """List open tasks."""
        res = await client.get("/api/tasks/")
        assert res.status_code == 200
        tasks = res.json()
        assert isinstance(tasks, list)

    @pytest.mark.asyncio
    async def test_search_tasks(self, client):
        """Search tasks by title."""
        res = await client.get("/api/tasks/?search=ceiling")
        assert res.status_code == 200
        tasks = res.json()
        assert len(tasks) >= 1
        assert "ceiling" in tasks[0]["title"].lower()

    @pytest.mark.asyncio
    async def test_get_task_detail(self, client):
        """Get specific task."""
        task_id = test_state.get("task_id")
        if not task_id:
            pytest.skip("No task created")

        res = await client.get(f"/api/tasks/{task_id}")
        assert res.status_code == 200
        assert res.json()["id"] == task_id


# ── Offer Tests ────────────────────────────────────────────────

class TestOffers:
    @pytest.mark.asyncio
    async def test_create_offer(self, client):
        """Provider makes an offer on a task."""
        task_id = test_state.get("task_id")
        if not task_id:
            pytest.skip("No task created")

        res = await client.post(f"/api/tasks/{task_id}/offers", json={
            "task_id": task_id,
            "offered_price": 350,
            "message": "I can fix this today",
        }, headers={"Authorization": f"Bearer {test_state['user2_token']}"})
        assert res.status_code == 201
        data = res.json()
        assert data["offered_price"] == 350
        test_state["offer_id"] = data["id"]

    @pytest.mark.asyncio
    async def test_list_offers(self, client):
        """List offers for a task."""
        task_id = test_state.get("task_id")
        if not task_id:
            pytest.skip("No task created")

        res = await client.get(
            f"/api/tasks/{task_id}/offers",
            headers={"Authorization": f"Bearer {test_state['user1_token']}"}
        )
        assert res.status_code == 200
        offers = res.json()
        assert len(offers) >= 1

    @pytest.mark.asyncio
    async def test_accept_offer(self, client):
        """Requester accepts an offer."""
        task_id = test_state.get("task_id")
        offer_id = test_state.get("offer_id")
        if not task_id or not offer_id:
            pytest.skip("No task/offer")

        res = await client.put(
            f"/api/tasks/{task_id}/offers/{offer_id}/accept",
            headers={"Authorization": f"Bearer {test_state['user1_token']}"}
        )
        assert res.status_code == 200


# ── Safety Tests ───────────────────────────────────────────────

class TestSafety:
    @pytest.mark.asyncio
    async def test_send_otp(self, client):
        """Send OTP to user phone."""
        res = await client.post("/api/safety/otp/send", json={
            "phone": "9876543210",
        })
        assert res.status_code == 200
        data = res.json()
        assert "dev_otp" in data  # Dev mode returns OTP

    @pytest.mark.asyncio
    async def test_report_user(self, client):
        """Report another user."""
        res = await client.post("/api/safety/reports", json={
            "reported_id": test_state["user2_id"],
            "reason": "spam",
            "description": "Test report",
        }, headers={"Authorization": f"Bearer {test_state['user1_token']}"})
        assert res.status_code == 201

    @pytest.mark.asyncio
    async def test_sos(self, client):
        """Trigger SOS alert."""
        res = await client.post(
            "/api/safety/sos",
            headers={"Authorization": f"Bearer {test_state['user1_token']}"}
        )
        assert res.status_code == 200
        assert "message" in res.json()


# ── Health Check ───────────────────────────────────────────────

class TestHealth:
    @pytest.mark.asyncio
    async def test_health(self, client):
        """Health endpoint works."""
        res = await client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

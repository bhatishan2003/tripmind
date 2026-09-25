"""End-to-end trip CRUD test with SQLite (no Postgres needed)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.db.database import Base, get_session
from app.db.models.user import User
from app.main import create_app

TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def client():
    engine = create_async_engine(TEST_DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as s:
        user = User(email="test@example.com", hashed_password=hash_password("secret123"), full_name="T")
        s.add(user)
        await s.commit()
        await s.refresh(user)
        uid = user.id

    async def override_session():
        async with Session() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.headers["Authorization"] = f"Bearer {create_access_token(str(uid))}"
        yield ac
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_and_get_trip(client: AsyncClient):
    payload = {
        "destination": "Kyoto",
        "start_date": "2026-04-01",
        "end_date": "2026-04-03",
        "budget": "2000.00",
        "currency": "USD",
        "travelers": 2,
        "travel_style": "balanced",
        "interests": ["culture", "food"],
    }
    r = await client.post("/api/v1/trips", json=payload)
    assert r.status_code == 201, r.text
    trip = r.json()
    assert trip["destination"] == "Kyoto"
    assert trip["itinerary"] is not None
    assert len(trip["itinerary"]["days"]) == 3

    r2 = await client.get(f"/api/v1/trips/{trip['id']}")
    assert r2.status_code == 200

    r3 = await client.get("/api/v1/trips")
    assert r3.status_code == 200
    assert len(r3.json()) >= 1

    r4 = await client.post(f"/api/v1/trips/{trip['id']}/generate")
    assert r4.status_code == 200

    r5 = await client.delete(f"/api/v1/trips/{trip['id']}")
    assert r5.status_code == 204

"""Phase 2 destination + RAG-grounded trip tests (SQLite, no Postgres)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.db.database import Base, get_session
from app.db.models.user import User
from app.main import create_app
from app.rag.ingest import RawDocument
from app.rag.store import upsert_document

TEST_DB = "sqlite+aiosqlite:///:memory:"
KYOTO_DOC = (
    "Gion is the famous geisha district of Kyoto. Stay here for machiya streets, "
    "Yasaka Shrine and tea houses. Higashiyama has temples on your doorstep. "
) * 8


@pytest.fixture
async def client():
    import app.db.models

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
        await upsert_document(
            s,
            RawDocument(
                source_uri="kyoto/areas-to-stay.md",
                title="Where to Stay in Kyoto",
                destination="Kyoto",
                category="areas-to-stay",
                checksum="abc",
                content=KYOTO_DOC,
            ),
        )

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
async def test_search_destinations(client: AsyncClient):
    r = await client.get("/api/v1/destinations/search")
    assert r.status_code == 200, r.text
    names = [d["destination"] for d in r.json()]
    assert "Kyoto" in names

    r2 = await client.get("/api/v1/destinations/search", params={"q": "kyo"})
    assert r2.status_code == 200
    assert [d["destination"] for d in r2.json()] == ["Kyoto"]


@pytest.mark.asyncio
async def test_get_destination_detail(client: AsyncClient):
    r = await client.get("/api/v1/destinations/Kyoto")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["destination"] == "Kyoto"
    assert body["document_count"] == 1
    assert "areas-to-stay" in body["categories"]
    assert body["documents"][0]["title"] == "Where to Stay in Kyoto"


@pytest.mark.asyncio
async def test_get_unknown_destination_404(client: AsyncClient):
    r = await client.get("/api/v1/destinations/Atlantis")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_created_trip_is_grounded_in_sources(client: AsyncClient):
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
    itinerary = r.json()["itinerary"]
    assert itinerary["sources"], "RAG corpus should ground the itinerary"
    assert itinerary["sources"][0]["source_uri"] == "kyoto/areas-to-stay.md"

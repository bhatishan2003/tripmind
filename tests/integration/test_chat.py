"""Persisted chat + SSE streaming tests (SQLite, no LLM/Postgres needed)."""

import json

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
    import app.db.models

    engine = create_async_engine(TEST_DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as s:
        user = User(email="chat@example.com", hashed_password=hash_password("secret123"), full_name="Chat")
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
async def test_chat_turn_and_history(client: AsyncClient):
    r = await client.post("/api/v1/chat", json={"message": "Plan a 5-day Goa trip for two"})
    assert r.status_code == 200, r.text
    body = r.json()

    conversation_id = body["conversation_id"]
    assert body["user_message"]["role"] == "user"
    assert body["user_message"]["content"] == "Plan a 5-day Goa trip for two"
    assert body["message"]["role"] == "assistant"
    assert body["message"]["content"].strip()

    history = await client.get(f"/api/v1/chat/{conversation_id}")
    assert history.status_code == 200, history.text
    payload = history.json()
    assert payload["id"] == conversation_id
    assert payload["title"]
    assert [m["role"] for m in payload["messages"]] == ["user", "assistant"]

    follow_up = await client.post(
        "/api/v1/chat",
        json={"conversation_id": conversation_id, "message": "Make day 3 cheaper"},
    )
    assert follow_up.status_code == 200, follow_up.text

    history2 = await client.get(f"/api/v1/chat/{conversation_id}")
    assert [m["role"] for m in history2.json()["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


@pytest.mark.asyncio
async def test_unknown_conversation_is_404(client: AsyncClient):
    r = await client.get("/api/v1/chat/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_streaming_chat_emits_deltas_and_persists(client: AsyncClient):
    created = await client.post("/api/v1/chat", json={"message": "Where should I stay in Kyoto?"})
    assert created.status_code == 200, created.text
    conversation_id = created.json()["conversation_id"]

    async with client.stream(
        "POST",
        "/api/v1/chat",
        json={"conversation_id": conversation_id, "message": "What about food markets?"},
        headers={"Accept": "text/event-stream"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        raw = "".join([chunk async for chunk in response.aiter_text()])

    events = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        lines = block.splitlines()
        event = next((line[6:].strip() for line in lines if line.startswith("event:")), "")
        data = next((line[5:].strip() for line in lines if line.startswith("data:")), "{}")
        events.append((event, json.loads(data)))

    kinds = [event for event, _ in events]
    assert "meta" in kinds
    assert "delta" in kinds
    assert "done" in kinds

    meta = next(data for event, data in events if event == "meta")
    assert meta["conversation_id"] == conversation_id
    assert meta["user_message"]["content"] == "What about food markets?"

    done = next(data for event, data in events if event == "done")
    assert done["message"]["role"] == "assistant"
    assert done["message"]["content"].strip()
    streamed_text = "".join(data["text"] for event, data in events if event == "delta")
    assert streamed_text.strip() == done["message"]["content"].strip()

    history = await client.get(f"/api/v1/chat/{conversation_id}")
    assert history.status_code == 200
    assert [m["role"] for m in history.json()["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]

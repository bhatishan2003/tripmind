"""Conversational trip assistant (Phase 2A).

Persistence, grounded context building, and LLM streaming all live here so the
API layer stays thin. The same golden rule as itinerary generation applies:
without an LLM key (or if the provider fails) we still answer deterministically
from the knowledge base, so offline dev and tests stay green.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import not_found
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.models.trip import Trip
from app.db.repositories import conversation as conversation_repo
from app.db.repositories import trip as trip_repo
from app.rag.retriever import hits_to_sources
from app.rag.store import semantic_search
from app.schemas.chat import ChatRequest, ConversationSummary
from app.schemas.itinerary import ItinerarySource
from app.services import itinerary_service

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 20
MAX_TITLE_LENGTH = 60
PREVIEW_LENGTH = 160

SYSTEM_PROMPT = """You are Tripmind, a practical and friendly travel assistant.
Help the user research destinations, shape itineraries, compare neighbourhoods,
and reason about budgets. Use the conversation history and the relevant local
knowledge provided below when it is available.

Rules:
- Ground recommendations in the supplied knowledge and cite source titles inline
  in the form [Source title] when you rely on them.
- Never invent prices, opening hours, availability, or booking confirmations.
  If you are unsure, say so and suggest how the user can verify.
- Be concise and useful. Use short paragraphs or bullet lists; no giant essays.
- You cannot book anything. You can help the user plan and then they can create
  a trip in the planner.
"""


def _title_from(message: str) -> str:
    title = " ".join(message.split())
    if len(title) <= MAX_TITLE_LENGTH:
        return title
    return title[: MAX_TITLE_LENGTH - 1].rstrip() + "…"


def _preview(text: str | None) -> str | None:
    if not text:
        return None
    preview = " ".join(text.split())
    if len(preview) <= PREVIEW_LENGTH:
        return preview
    return preview[: PREVIEW_LENGTH - 1].rstrip() + "…"


def _knowledge_block(sources: list[ItinerarySource]) -> str:
    usable = [s for s in sources if s.snippet]
    if not usable:
        return ""
    lines = "\n".join(f"- [{s.title}] {s.snippet}" for s in usable)
    return f"\nRelevant local knowledge (do not invent facts beyond this):\n{lines}\n"


def _trip_context(trip: Trip | None) -> str:
    if trip is None:
        return ""
    interests = ", ".join(trip.interests or []) or "general"
    return (
        f"\nThe conversation is bound to this trip:\n"
        f"- Destination: {trip.destination}\n"
        f"- Dates: {trip.start_date} to {trip.end_date}\n"
        f"- Budget: {trip.budget} {trip.currency}\n"
        f"- Travelers: {trip.travelers}\n"
        f"- Style: {trip.travel_style}\n"
        f"- Interests: {interests}\n"
    )


def _build_system_prompt(trip: Trip | None, sources: list[ItinerarySource]) -> str:
    today = datetime.now(UTC).date().isoformat()
    return f"{SYSTEM_PROMPT}\nToday's date: {today}.{_trip_context(trip)}{_knowledge_block(sources)}"


async def _retrieve_sources(
    session: AsyncSession,
    message: str,
    trip: Trip | None,
) -> list[ItinerarySource]:
    """Best-effort semantic search over the message; never blocks a reply."""
    try:
        filters = {"destination": trip.destination} if trip is not None else None
        hits = await semantic_search(session, message, top_k=settings.RAG_TOP_K, filters=filters)
        if not hits and filters is not None:
            hits = await semantic_search(session, message, top_k=settings.RAG_TOP_K, filters=None)
        return hits_to_sources(hits)
    except Exception as exc:  # noqa: BLE001 - knowledge base is optional infrastructure
        logger.warning("Chat retrieval unavailable (%s) — replying without RAG context", exc)
        return []


async def start_turn(
    session: AsyncSession,
    user_id: uuid.UUID,
    payload: ChatRequest,
) -> tuple[Conversation, Message]:
    """Resolve/create the conversation and persist the user's message."""
    trip: Trip | None = None
    if payload.trip_id is not None:
        trip = await trip_repo.get_owned(session, user_id, payload.trip_id)
        if trip is None:
            raise not_found("Trip not found")

    if payload.conversation_id is not None:
        conversation = await conversation_repo.get_owned(session, user_id, payload.conversation_id)
        if conversation is None:
            raise not_found("Conversation not found")
        if trip is not None and conversation.trip_id is None:
            conversation.trip_id = trip.id
        if not conversation.title:
            conversation.title = _title_from(payload.message)
    else:
        conversation = await conversation_repo.create_conversation(
            session,
            user_id=user_id,
            title=_title_from(payload.message),
            trip_id=trip.id if trip is not None else None,
        )

    user_message = await conversation_repo.add_message(
        session,
        conversation,
        role="user",
        content=payload.message,
    )
    return conversation, user_message


async def build_context(
    session: AsyncSession,
    conversation: Conversation,
    user_message: Message,
) -> tuple[list[dict[str, str]], list[ItinerarySource], Trip | None]:
    """Build provider-agnostic chat messages plus citable RAG sources."""
    trip = await session.get(Trip, conversation.trip_id) if conversation.trip_id is not None else None
    sources = await _retrieve_sources(session, user_message.content, trip)
    history = await conversation_repo.list_messages(session, conversation.id, limit=MAX_HISTORY_MESSAGES)

    messages: list[dict[str, str]] = [{"role": "system", "content": _build_system_prompt(trip, sources)}]
    for item in history:
        if item.role in {"user", "assistant"}:
            messages.append({"role": item.role, "content": item.content})
    return messages, sources, trip


def fallback_reply(
    user_message: str,
    sources: list[ItinerarySource],
    trip: Trip | None,
) -> str:
    """Deterministic, useful reply when no LLM is configured."""
    if sources:
        notes = "\n".join(f"- [{s.title}] {s.snippet}" for s in sources[:3] if s.snippet)
        opening = "I'm running without an LLM key, so here are the most relevant notes from the knowledge base:"
        if notes:
            return f"{opening}\n\n{notes}\n\nAsk me to expand on any of these, or configure an LLM key for a conversational answer."
    if trip is not None:
        return (
            "I'm running without an LLM key, so I can't generate a conversational answer yet. "
            f"Your conversation is attached to the {trip.destination} trip "
            f"({trip.start_date} → {trip.end_date}, {trip.budget} {trip.currency}). "
            "You can still use the planner to regenerate the itinerary, or add an LLM key to chat freely."
        )
    return (
        "I'm running without an LLM key, so I can't generate a conversational answer yet. "
        "Add GROQ_API_KEY or OPENAI_API_KEY to .env to enable free-form chat. "
        f"In the meantime, I received: “{user_message.strip()}”."
    )


def _tokenize(text: str) -> list[str]:
    """Split into word-sized chunks so the offline fallback still streams."""
    return re.findall(r"\S+\s*", text)


def _resolve_client() -> tuple[object, str, str] | None:
    """Return (AsyncOpenAI client, provider, model) or None for fallback."""
    resolved = itinerary_service._resolve_llm()
    if resolved is None:
        return None
    provider, api_key, model, base_url = resolved

    from openai import AsyncOpenAI

    kwargs: dict = {"api_key": api_key, "timeout": settings.LLM_TIMEOUT_SECONDS}
    if base_url:
        kwargs["base_url"] = base_url
    return AsyncOpenAI(**kwargs), provider, model


async def complete_reply(messages: list[dict[str, str]], *, fallback: str) -> str:
    """One-shot completion (non-streaming POST /chat)."""
    resolved = _resolve_client()
    if resolved is None:
        return fallback
    client, provider, model = resolved
    try:
        logger.info("Chat completion provider=%s model=%s", provider, model)
        response = await client.chat.completions.create(  # type: ignore[attr-defined]
            model=model,
            messages=messages,
            temperature=0.6,
        )
        content = (response.choices[0].message.content or "").strip()
        return content or fallback
    except Exception as exc:  # noqa: BLE001 - any provider failure falls back
        logger.warning("Chat LLM call failed (%s) — falling back to template", exc)
        return fallback


async def stream_reply(
    messages: list[dict[str, str]],
    *,
    fallback: str,
) -> AsyncIterator[str]:
    """Yield reply text incrementally (SSE). Falls back if the provider fails."""
    resolved = _resolve_client()
    if resolved is None:
        for token in _tokenize(fallback):
            yield token
        return

    client, provider, model = resolved
    emitted = False
    try:
        logger.info("Chat streaming provider=%s model=%s", provider, model)
        stream = await client.chat.completions.create(  # type: ignore[attr-defined]
            model=model,
            messages=messages,
            temperature=0.6,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            content = getattr(chunk.choices[0].delta, "content", None)
            if content:
                emitted = True
                yield content
    except Exception as exc:  # noqa: BLE001 - provider/network errors are non-fatal
        logger.warning("Chat streaming failed after %s chunk(s): %s", emitted, exc)
        if not emitted:
            for token in _tokenize(fallback):
                yield token
        else:
            yield "\n\n_(The response was interrupted — please try again.)_"
        return

    if not emitted:
        for token in _tokenize(fallback):
            yield token


async def finish_turn(
    session: AsyncSession,
    conversation: Conversation,
    *,
    content: str,
    sources: list[ItinerarySource],
) -> Message:
    """Persist the assistant reply with its citations."""
    return await conversation_repo.add_message(
        session,
        conversation,
        role="assistant",
        content=content,
        sources=[source.model_dump() for source in sources],
    )


async def get_history(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> Conversation:
    conversation = await conversation_repo.get_owned(session, user_id, conversation_id, with_messages=True)
    if conversation is None:
        raise not_found("Conversation not found")
    return conversation


async def list_conversations(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[ConversationSummary]:
    rows = await conversation_repo.list_by_user(session, user_id, limit=limit, offset=offset)
    return [
        ConversationSummary(
            id=conversation.id,
            title=conversation.title,
            trip_id=conversation.trip_id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            last_message=_preview(preview),
            last_role=last_role,
            message_count=message_count,
        )
        for conversation, preview, last_role, message_count in rows
    ]


async def delete_conversation(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> None:
    conversation = await conversation_repo.get_owned(session, user_id, conversation_id)
    if conversation is None:
        raise not_found("Conversation not found")
    await conversation_repo.delete(session, conversation)


async def reply(
    session: AsyncSession,
    user_id: uuid.UUID,
    payload: ChatRequest,
) -> tuple[Conversation, Message, Message]:
    """Run a full non-streaming turn: persist user + assistant messages."""
    conversation, user_message = await start_turn(session, user_id, payload)
    messages, sources, trip = await build_context(session, conversation, user_message)
    fallback = fallback_reply(user_message.content, sources, trip)
    content = await complete_reply(messages, fallback=fallback)
    assistant = await finish_turn(session, conversation, content=content, sources=sources)
    return conversation, user_message, assistant

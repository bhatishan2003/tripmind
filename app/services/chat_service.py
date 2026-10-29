"""Conversational trip assistant (Phase 2A & 2B Agentic Upgrade).

Persistence, grounded context building, LLM streaming, and function-calling
agent loop live here. Tools for trip management, itinerary editing, live weather,
currency conversion, and local knowledge are executed automatically during chat turns.
Without an LLM key (or if the provider fails) we answer deterministically
from the knowledge base, so offline dev and tests stay green.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

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
from app.services import tools as agent_tools

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 20
MAX_TITLE_LENGTH = 60
PREVIEW_LENGTH = 160
MAX_AGENT_ITERATIONS = 5

SYSTEM_PROMPT = """You are Tripmind, a practical, capable, and friendly travel assistant and planner.
Help the user research destinations, shape itineraries, compare neighbourhoods, reason about budgets, check live weather, and convert currencies. Use the conversation history, available tools, and relevant local knowledge provided below.

Agent Capabilities & Tool Instructions:
- You have real tools connected to the database and live APIs:
  * `create_trip`: When user wants to plan or create a new trip (destination, dates, budget, etc.).
  * `modify_itinerary`: When user wants to change, add, or remove activities or days in an itinerary (e.g. "Add a 4th day to my Kyoto trip", "Change Day 2 dinner to an authentic ramen shop", "Add an afternoon visit to Arashiyama").
  * `update_trip`: When user wants to update top-level constraints like dates, budget, travel style, or traveler count.
  * `list_my_trips` and `get_trip`: When user asks to see or inspect their saved trips or day-by-day plan.
  * `delete_trip`: Only delete when the user explicitly provides confirmation='confirm delete'. If the user says "delete my trip", ask them to confirm first before calling delete_trip.
  * `get_weather_forecast`: Live weather, rain probabilities, warnings, and packing advice via Open-Meteo.
  * `convert_currency`: Real-time foreign exchange currency conversion via Frankfurter.
  * `search_knowledge`, `search_restaurants`, `search_activities`, `search_hotels`: Search local travel guides and curated knowledge.

Rules:
- ALWAYS invoke the appropriate tool when the user asks you to modify an itinerary, plan a trip, check weather, convert currency, or manage trips.
- After a tool executes, provide a clear, concise, and helpful response summarizing what was done.
- Ground recommendations in the supplied knowledge and cite source titles inline when you rely on them.
- Never invent booking confirmations, flight tickets, or prices without grounding.
- Be concise and structured. Use short paragraphs or bullet lists; no endless essays.
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
    return f"\nRelevant local knowledge (ground recommendations in these; cite [Title]):\n{lines}\n"


def _trip_context(trip: Trip | None) -> str:
    if trip is None:
        return ""
    interests = ", ".join(trip.interests or []) or "general"
    days_summary: list[str] = []
    if trip.itinerary and isinstance(trip.itinerary, dict) and "days" in trip.itinerary:
        for d in trip.itinerary["days"]:
            act_titles = [a.get("title") for a in d.get("activities", []) if isinstance(a, dict) and a.get("title")]
            days_summary.append(
                f"  * Day {d.get('day_number')} ({d.get('date')} - {d.get('theme', '')}): {', '.join(act_titles[:3])}"
            )
    days_text = ("\nCurrent Itinerary Schedule:\n" + "\n".join(days_summary)) if days_summary else ""

    return (
        f"\nThe conversation is bound to this trip:\n"
        f"- Trip ID: {trip.id}\n"
        f"- Destination: {trip.destination}\n"
        f"- Dates: {trip.start_date} to {trip.end_date}\n"
        f"- Budget: {trip.budget} {trip.currency}\n"
        f"- Travelers: {trip.travelers}\n"
        f"- Style: {trip.travel_style}\n"
        f"- Interests: {interests}\n"
        f"{days_text}\n"
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
) -> tuple[list[dict[str, Any]], list[ItinerarySource], Trip | None]:
    """Build provider-agnostic chat messages plus citable RAG sources."""
    trip = await session.get(Trip, conversation.trip_id) if conversation.trip_id is not None else None
    sources = await _retrieve_sources(session, user_message.content, trip)
    history = await conversation_repo.list_messages(session, conversation.id, limit=MAX_HISTORY_MESSAGES)

    messages: list[dict[str, Any]] = [{"role": "system", "content": _build_system_prompt(trip, sources)}]
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
            return f"{opening}\n\n{notes}\n\nAsk me to expand on any of these, or configure an LLM key for conversational planning."
    if trip is not None:
        return (
            "I'm running without an LLM key, so I can't generate a conversational answer yet. "
            f"Your conversation is attached to the {trip.destination} trip "
            f"({trip.start_date} → {trip.end_date}, {trip.budget} {trip.currency}). "
            "You can still use the planner to regenerate the itinerary, or add an LLM key to chat freely."
        )
    return (
        "I'm running without an LLM key, so I can't generate a conversational answer yet. "
        "Add GROQ_API_KEY to .env to enable free-form agent chat. "
        f"In the meantime, I received: “{user_message.strip()}”."
    )


def _tokenize(text: str) -> list[str]:
    """Split into word-sized chunks so the offline fallback still streams."""
    return re.findall(r"\S+\s*", text)


def _resolve_clients() -> list[tuple[object, str, str]]:
    """Return configured AsyncOpenAI clients in priority order, or [] for fallback."""
    if itinerary_service._resolve_llm() is None:
        return []

    from openai import AsyncOpenAI

    clients: list[tuple[object, str, str]] = []
    for provider, api_key, model, base_url in itinerary_service._llm_candidates():
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": settings.LLM_TIMEOUT_SECONDS}
        if base_url:
            kwargs["base_url"] = base_url
        clients.append((AsyncOpenAI(**kwargs), provider, model))
    return clients


async def complete_reply(
    messages: list[dict[str, Any]],
    *,
    fallback: str,
    session: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
) -> str:
    """One-shot completion with agentic tool execution loop (max 5 iterations)."""
    clients = _resolve_clients()
    if not clients:
        return fallback

    for client, provider, model in clients:
        conversation_messages = [dict(m) for m in messages]
        try:
            for iteration in range(1, MAX_AGENT_ITERATIONS + 1):
                logger.info("Chat completion provider=%s model=%s iteration=%d", provider, model, iteration)
                response = await client.chat.completions.create(  # type: ignore[attr-defined]
                    model=model,
                    messages=conversation_messages,
                    tools=agent_tools.TOOLS,
                    tool_choice="auto",
                    temperature=0.6,
                )
                choice = response.choices[0]
                msg = choice.message

                if msg.tool_calls:
                    assistant_turn: dict[str, Any] = {
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in msg.tool_calls
                        ],
                    }
                    conversation_messages.append(assistant_turn)

                    for tc in msg.tool_calls:
                        fn_name = tc.function.name
                        try:
                            fn_args = json.loads(tc.function.arguments or "{}")
                        except (json.JSONDecodeError, TypeError):
                            fn_args = {}
                        tool_result = await agent_tools.execute_tool(fn_name, fn_args, session=session, user_id=user_id)
                        conversation_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": fn_name,
                                "content": tool_result,
                            }
                        )
                    continue

                content = (msg.content or "").strip()
                if content:
                    return content
                logger.warning("Chat provider=%s returned empty content on iteration %d", provider, iteration)
        except Exception as exc:  # noqa: BLE001 - any provider failure falls through
            logger.warning("Chat provider=%s failed (%s)", provider, exc)

    return fallback


async def stream_reply(
    messages: list[dict[str, Any]],
    *,
    fallback: str,
    session: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
) -> AsyncIterator[str]:
    """Yield reply text incrementally (SSE) with full tool execution agent loop."""
    clients = _resolve_clients()
    if not clients:
        for token in _tokenize(fallback):
            yield token
        return

    for client, provider, model in clients:
        emitted = False
        conversation_messages = [dict(m) for m in messages]
        try:
            for iteration in range(1, MAX_AGENT_ITERATIONS + 1):
                logger.info("Chat streaming provider=%s model=%s iteration=%d", provider, model, iteration)
                stream = await client.chat.completions.create(  # type: ignore[attr-defined]
                    model=model,
                    messages=conversation_messages,
                    tools=agent_tools.TOOLS,
                    tool_choice="auto",
                    temperature=0.6,
                    stream=True,
                )

                accumulated_tool_calls: dict[int, dict[str, Any]] = {}
                accumulated_content: list[str] = []

                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta

                    # Accumulate tool calls if any
                    delta_tool_calls = getattr(delta, "tool_calls", None)
                    if delta_tool_calls:
                        for tc_chunk in delta_tool_calls:
                            idx = getattr(tc_chunk, "index", 0)
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": tc_chunk.id or f"call_{idx}_{uuid.uuid4().hex[:8]}",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            if tc_chunk.id:
                                accumulated_tool_calls[idx]["id"] = tc_chunk.id
                            fn = getattr(tc_chunk, "function", None)
                            if fn:
                                if fn.name:
                                    accumulated_tool_calls[idx]["function"]["name"] += fn.name
                                if fn.arguments:
                                    accumulated_tool_calls[idx]["function"]["arguments"] += fn.arguments

                    # Stream text tokens directly to user
                    content = getattr(delta, "content", None)
                    if content:
                        emitted = True
                        accumulated_content.append(content)
                        yield content

                if accumulated_tool_calls:
                    # Assistant chose to call tools
                    tool_calls_list = list(accumulated_tool_calls.values())
                    conversation_messages.append(
                        {
                            "role": "assistant",
                            "content": "".join(accumulated_content) if accumulated_content else None,
                            "tool_calls": tool_calls_list,
                        }
                    )

                    for tc in tool_calls_list:
                        fn_name = tc["function"]["name"]
                        try:
                            fn_args = json.loads(tc["function"]["arguments"] or "{}")
                        except (json.JSONDecodeError, TypeError):
                            fn_args = {}
                        tool_result = await agent_tools.execute_tool(fn_name, fn_args, session=session, user_id=user_id)
                        conversation_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "name": fn_name,
                                "content": tool_result,
                            }
                        )
                    continue

                if emitted:
                    return

            if emitted:
                return
            logger.warning("Chat provider=%s returned no content", provider)
        except Exception as exc:  # noqa: BLE001 - provider/network errors are non-fatal
            logger.warning("Chat streaming provider=%s failed after %s chunk(s): %s", provider, emitted, exc)
            if emitted:
                yield "\n\n_(The response was interrupted — please try again.)_"
                return

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
    content = await complete_reply(messages, fallback=fallback, session=session, user_id=user_id)
    assistant = await finish_turn(session, conversation, content=content, sources=sources)
    return conversation, user_message, assistant

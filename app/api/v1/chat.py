"""Conversational trip assistant endpoints (Phase 2A).

GET  /chat          — list the user's conversations (history sidebar)
POST /chat          — one turn (JSON, or SSE with `stream` / Accept header)
POST /chat/stream   — one turn streamed as Server-Sent Events
GET  /chat/{id}     — persisted conversation transcript
DELETE /chat/{id}   — delete a conversation and its messages
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import get_current_user
from app.db.database import AsyncSessionLocal, get_session
from app.db.models.conversation import Conversation
from app.db.models.user import User
from app.db.repositories import conversation as conversation_repo
from app.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatTurn,
    ConversationRead,
    ConversationSummary,
)
from app.services import chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/ping")
async def ping():
    return {"status": "ready"}


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    session: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    return await chat_service.list_conversations(session, current.id, limit=limit, offset=offset)


@router.post("", response_model=None)
async def chat(
    payload: ChatRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[User, Depends(get_current_user)],
):
    """One chat turn.

    Returns JSON by default. If the body sets `stream: true` (or the client
    sends `Accept: text/event-stream`) the same turn is returned as SSE.
    """
    wants_stream = payload.stream or "text/event-stream" in request.headers.get("accept", "").lower()
    if wants_stream:
        return await _stream_turn(payload, session, current)

    conversation, user_message, assistant = await chat_service.reply(session, current.id, payload)
    return ChatTurn(
        conversation_id=conversation.id,
        user_message=ChatMessage.model_validate(user_message),
        message=ChatMessage.model_validate(assistant),
    )


@router.post("/stream", response_model=None)
async def stream_chat(
    payload: ChatRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[User, Depends(get_current_user)],
):
    return await _stream_turn(payload, session, current)


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[User, Depends(get_current_user)],
):
    return await chat_service.get_history(session, current.id, conversation_id)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[User, Depends(get_current_user)],
):
    await chat_service.delete_conversation(session, current.id, conversation_id)


async def _stream_turn(
    payload: ChatRequest,
    session: AsyncSession,
    current: User,
) -> StreamingResponse:
    conversation, user_message = await chat_service.start_turn(session, current.id, payload)
    messages, sources, trip = await chat_service.build_context(session, conversation, user_message)
    fallback = chat_service.fallback_reply(user_message.content, sources, trip)

    conversation_id = conversation.id
    user_payload = ChatMessage.model_validate(user_message).model_dump(mode="json")
    source_payload = [source.model_dump() for source in sources]

    # The request-scoped session may be closed once the response starts; the
    # generator owns a fresh session bound to the same engine instead.
    bind = getattr(session, "bind", None)
    session_factory = async_sessionmaker(bind, expire_on_commit=False) if bind is not None else AsyncSessionLocal

    async def event_stream():
        yield _sse("meta", {"conversation_id": str(conversation_id), "user_message": user_payload})
        pieces: list[str] = []
        try:
            async for token in chat_service.stream_reply(messages, fallback=fallback):
                pieces.append(token)
                yield _sse("delta", {"text": token})
        except asyncio.CancelledError:
            # Client hit Stop/closed the tab — keep whatever was generated.
            if pieces:
                try:
                    await _save_assistant(session_factory, conversation_id, "".join(pieces).strip(), source_payload)
                except Exception:
                    logger.exception("Could not persist partial chat reply")
            raise
        except Exception:  # the stream must not die mid-turn
            logger.exception("Chat stream failed")
            yield _sse("error", {"detail": "The assistant hit an error. Please try again."})
            return

        content = "".join(pieces).strip() or fallback
        try:
            assistant = await _save_assistant(session_factory, conversation_id, content, source_payload)
        except Exception:
            logger.exception("Could not persist chat reply")
            yield _sse("error", {"detail": "Reply generated but could not be saved."})
            return

        yield _sse(
            "done",
            {
                "conversation_id": str(conversation_id),
                "message": ChatMessage.model_validate(assistant).model_dump(mode="json"),
            },
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _save_assistant(session_factory, conversation_id: uuid.UUID, content: str, sources: list):
    async with session_factory() as session:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None:
            raise RuntimeError("Conversation disappeared before the reply was saved")
        return await conversation_repo.add_message(
            session,
            conversation,
            role="assistant",
            content=content,
            sources=sources,
        )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"

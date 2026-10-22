"""Conversation + message repository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.conversation import Conversation
from app.db.models.message import Message


async def create_conversation(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    title: str | None = None,
    trip_id: uuid.UUID | None = None,
) -> Conversation:
    conversation = Conversation(user_id=user_id, title=title, trip_id=trip_id)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def get_owned(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    with_messages: bool = False,
) -> Conversation | None:
    stmt = select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    if with_messages:
        stmt = stmt.options(selectinload(Conversation.messages))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_by_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[tuple[Conversation, str | None, str | None, int]]:
    """Conversation summaries, newest activity first, with a last-message preview."""
    last_message = (
        select(Message.content)
        .where(Message.conversation_id == Conversation.id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
        .correlate(Conversation)
        .scalar_subquery()
    )
    last_role = (
        select(Message.role)
        .where(Message.conversation_id == Conversation.id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
        .correlate(Conversation)
        .scalar_subquery()
    )
    message_count = (
        select(func.count(Message.id))
        .where(Message.conversation_id == Conversation.id)
        .correlate(Conversation)
        .scalar_subquery()
    )

    stmt = (
        select(
            Conversation,
            last_message.label("last_message"),
            last_role.label("last_role"),
            message_count.label("message_count"),
        )
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).all()
    return [(conversation, preview, role, int(count or 0)) for conversation, preview, role, count in rows]


async def list_messages(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    limit: int | None = None,
) -> list[Message]:
    """Messages in chronological order; `limit` returns the most recent N."""
    if limit:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        rows = list((await session.execute(stmt)).scalars().all())
        rows.reverse()
        return rows
    stmt = (
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc(), Message.id.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def add_message(
    session: AsyncSession,
    conversation: Conversation,
    *,
    role: str,
    content: str,
    sources: list | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
        sources=sources or [],
    )
    conversation.updated_at = datetime.now(UTC)
    session.add(message)
    session.add(conversation)
    await session.commit()
    await session.refresh(message)
    return message


async def delete(session: AsyncSession, conversation: Conversation) -> None:
    await session.delete(conversation)
    await session.commit()

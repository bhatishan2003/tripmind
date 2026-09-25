"""User repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def create(session: AsyncSession, *, email: str, hashed_password: str, full_name: str | None) -> User:
    user = User(email=email, hashed_password=hashed_password, full_name=full_name)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

"""Auth dependencies: current user from Bearer JWT."""

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Unauthorized, not_found
from app.core.security import decode_token
from app.db.database import get_session
from app.db.models.user import User
from app.db.repositories import user as user_repo

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if creds is None or not creds.credentials:
        raise Unauthorized
    user_id = decode_token(creds.credentials)
    if not user_id:
        raise Unauthorized
    try:
        user = await user_repo.get_by_id(session, uuid.UUID(user_id))
    except ValueError:
        raise Unauthorized
    if not user:
        raise not_found("User not found")
    return user

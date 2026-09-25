"""Auth endpoints: register / login / me."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.exceptions import bad_request
from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import get_session
from app.db.models.user import User
from app.db.repositories import user as user_repo
from app.schemas.user import LoginRequest, Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
async def register(payload: UserCreate, session: Annotated[AsyncSession, Depends(get_session)]):
    if await user_repo.get_by_email(session, payload.email):
        raise bad_request("Email already registered")
    user = await user_repo.create(
        session,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    return user


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, session: Annotated[AsyncSession, Depends(get_session)]):
    user = await user_repo.get_by_email(session, payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise bad_request("Invalid email or password")
    return Token(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserRead)
async def me(current: Annotated[User, Depends(get_current_user)]):
    return current

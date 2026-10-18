"""Destination knowledge-base endpoints (Phase 2)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.exceptions import not_found
from app.db.database import get_session
from app.db.models.user import User
from app.schemas.destination import DestinationDetail, DestinationSummary
from app.services import destination_service

router = APIRouter(prefix="/destinations", tags=["destinations"])


@router.get("/search", response_model=list[DestinationSummary])
async def search_destinations(
    current: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str | None = Query(default=None, description="Filter destinations by name"),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Search destinations available in the RAG knowledge base."""
    return await destination_service.search_destinations(session, q, limit=limit)


@router.get("/{name}", response_model=DestinationDetail)
async def get_destination(
    name: str,
    current: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Knowledge-base documents for a single destination."""
    detail = await destination_service.get_destination(session, name)
    if detail is None:
        raise not_found(f"No knowledge base entries for destination '{name}'")
    return detail

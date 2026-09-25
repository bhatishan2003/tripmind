"""Shared schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    environment: str


class PaginatedMeta(BaseModel):
    total: int
    limit: int
    offset: int

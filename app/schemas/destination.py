"""Destination knowledge-base schemas (Phase 2)."""

from pydantic import BaseModel, Field


class DestinationSummary(BaseModel):
    destination: str
    document_count: int = 0
    categories: list[str] = Field(default_factory=list)


class DestinationDocument(BaseModel):
    id: str
    title: str
    source_uri: str
    category: str | None = None
    snippet: str = ""


class DestinationDetail(BaseModel):
    destination: str
    document_count: int = 0
    categories: list[str] = Field(default_factory=list)
    documents: list[DestinationDocument] = Field(default_factory=list)

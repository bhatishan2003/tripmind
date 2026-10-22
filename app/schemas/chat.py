"""Chat request/response schemas (Phase 2A: persisted conversational Q&A)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.itinerary import ItinerarySource


class ChatRequest(BaseModel):
    """One user turn. Omit `conversation_id` to start a new conversation."""

    message: str = Field(min_length=1, max_length=8000)
    conversation_id: uuid.UUID | None = None
    trip_id: uuid.UUID | None = None
    # POST /chat streams when this is true (or when Accept is text/event-stream).
    stream: bool = False

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message cannot be empty")
        return value


class ChatMessage(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    sources: list[ItinerarySource] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatTurn(BaseModel):
    conversation_id: uuid.UUID
    user_message: ChatMessage
    message: ChatMessage


class ConversationRead(BaseModel):
    id: uuid.UUID
    title: str | None = None
    trip_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessage] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    """Lightweight row for the chat history sidebar (no transcript payload)."""

    id: uuid.UUID
    title: str | None = None
    trip_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    last_message: str | None = None
    last_role: str | None = None
    message_count: int = 0

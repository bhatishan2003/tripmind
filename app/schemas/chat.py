"""Placeholder for Phase 2 conversational trip chat."""

from pydantic import BaseModel


class ChatMessage(BaseModel):
    message: str

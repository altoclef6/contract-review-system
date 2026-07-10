from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ChatRole(StrEnum):
    user = "user"
    assistant = "assistant"


class ChatMessage(BaseModel):
    id: str
    role: ChatRole
    content: str
    created_at: datetime


class ChatSessionCreate(BaseModel):
    review_id: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=100)


class ChatSessionPublic(BaseModel):
    id: str
    owner_id: str
    review_id: str | None = None
    title: str
    messages: list[ChatMessage]
    created_at: datetime
    updated_at: datetime


class ChatAskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatAskResponse(BaseModel):
    session: ChatSessionPublic
    answer: ChatMessage
    ai_available: bool

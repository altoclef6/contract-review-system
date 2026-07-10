from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NotificationPublic(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    content: str
    is_read: bool
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationPublic]
    unread_count: int
    total: int

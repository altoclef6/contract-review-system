from typing import Any

from pydantic import BaseModel


class SystemStatus(BaseModel):
    status: str
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    metrics: dict[str, Any]
    database_enabled: bool
    redis_enabled: bool

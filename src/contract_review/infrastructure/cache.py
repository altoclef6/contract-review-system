from __future__ import annotations

import json
import logging
from typing import Any

from contract_review.core.config import Settings

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.redis_enabled
        self.default_ttl = settings.cache_ttl_seconds
        self._client: Any | None = None
        if self.enabled:
            try:
                from redis import Redis

                self._client = Redis.from_url(
                    settings.redis_url.get_secret_value(), decode_responses=True
                )
            except Exception as exc:  # pragma: no cover - environment dependent
                logger.warning("Redis initialization failed: %s", exc)
                self.enabled = False

    def get_json(self, key: str) -> Any | None:
        if not self.enabled or self._client is None:
            return None
        try:
            value = self._client.get(key)
            return json.loads(value) if value else None
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("Redis read failed: %s", exc)
            return None

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> bool:
        if not self.enabled or self._client is None:
            return False
        try:
            self._client.setex(
                key,
                ttl or self.default_ttl,
                json.dumps(value, ensure_ascii=False, default=str),
            )
            return True
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("Redis write failed: %s", exc)
            return False

    def delete(self, *keys: str) -> int:
        if not self.enabled or self._client is None or not keys:
            return 0
        try:
            return int(self._client.delete(*keys))
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("Redis delete failed: %s", exc)
            return 0

    def ping(self) -> bool:
        if not self.enabled or self._client is None:
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            return False

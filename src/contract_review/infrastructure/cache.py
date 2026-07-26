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
        _, value = self.get_json_status(key)
        return value

    def get_json_status(self, key: str) -> tuple[bool, Any | None]:
        if not self.enabled or self._client is None:
            return False, None
        try:
            value = self._client.get(key)
            return True, json.loads(value) if value else None
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("Redis read failed: %s", exc)
            return False, None

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

    def increment_window(self, key: str, ttl: int) -> int | None:
        if not self.enabled or self._client is None:
            return None
        try:
            pipeline = self._client.pipeline()
            pipeline.incr(key)
            pipeline.expire(key, ttl, nx=True)
            count, _ = pipeline.execute()
            return int(count)
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("Redis counter failed: %s", exc)
            return None

    def set_if_absent_json(self, key: str, value: Any, ttl: int) -> bool:
        if not self.enabled or self._client is None:
            return False
        try:
            return bool(
                self._client.set(
                    key,
                    json.dumps(value, ensure_ascii=False, default=str),
                    ex=ttl,
                    nx=True,
                )
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("Redis lock failed: %s", exc)
            return False

    def delete(self, *keys: str) -> int:
        if not self.enabled or self._client is None or not keys:
            return 0
        try:
            return int(self._client.delete(*keys))
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("Redis delete failed: %s", exc)
            return 0

    def delete_if_json(self, key: str, value: Any) -> bool:
        if not self.enabled or self._client is None:
            return False
        expected = json.dumps(value, ensure_ascii=False, default=str)
        script = (
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end"
        )
        try:
            return bool(self._client.eval(script, 1, key, expected))
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("Redis lock release failed: %s", exc)
            return False

    def ping(self) -> bool:
        if not self.enabled or self._client is None:
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            return False

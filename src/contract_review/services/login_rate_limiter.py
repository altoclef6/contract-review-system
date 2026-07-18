from __future__ import annotations

import hashlib
import threading
from collections import defaultdict, deque
from time import time

from contract_review.core.config import Settings
from contract_review.infrastructure.cache import CacheService


class LoginRateLimitExceeded(ValueError):
    pass


class LoginRateLimitUnavailable(RuntimeError):
    pass


class LoginRateLimiter:
    _lock = threading.Lock()
    _attempts: dict[str, deque[float]] = defaultdict(deque)

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cache = CacheService(settings)

    def check(self, *, email: str, client_ip: str | None) -> str:
        key = self._key(email, client_ip)
        if self.settings.redis_enabled:
            available, count = self.cache.get_json_status(key)
            if not available:
                raise LoginRateLimitUnavailable("login limiter storage unavailable")
            if count is None:
                return key
            if int(count) >= self.settings.login_max_attempts:
                raise LoginRateLimitExceeded("too many login attempts")
            return key
        now = time()
        with self._lock:
            bucket = self._attempts[key]
            while bucket and bucket[0] <= now - self.settings.login_window_seconds:
                bucket.popleft()
            if len(bucket) >= self.settings.login_max_attempts:
                raise LoginRateLimitExceeded("too many login attempts")
        return key

    def failed(self, key: str) -> None:
        if self.settings.redis_enabled:
            count = self.cache.increment_window(key, self.settings.login_window_seconds)
            if count is None:
                raise LoginRateLimitUnavailable("login limiter storage unavailable")
            return
        with self._lock:
            self._attempts[key].append(time())

    def succeeded(self, key: str) -> None:
        if self.settings.redis_enabled:
            self.cache.delete(key)
            return
        with self._lock:
            self._attempts.pop(key, None)

    def _key(self, email: str, client_ip: str | None) -> str:
        identity = f"{email.casefold()}|{client_ip or 'unknown'}".encode()
        return f"login-attempts:{hashlib.sha256(identity).hexdigest()}"

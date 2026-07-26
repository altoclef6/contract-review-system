from __future__ import annotations

import re
import secrets
import threading
from collections import defaultdict, deque
from time import perf_counter, time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from contract_review.core.logging import reset_request_id, set_request_id
from contract_review.core.metrics import metrics_registry


class DesktopStartupTokenMiddleware(BaseHTTPMiddleware):
    _public_paths = {"/api/v1/health/live", "/api/v1/health/ready"}

    def __init__(self, app: ASGIApp, startup_token: str) -> None:
        super().__init__(app)
        self.startup_token = startup_token

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self._public_paths:
            return await call_next(request)
        supplied = request.headers.get("x-desktop-startup-token", "")
        if not supplied or not secrets.compare_digest(supplied, self.startup_token):
            return JSONResponse(
                status_code=401,
                content={
                    "code": 40110,
                    "message": "desktop startup token is invalid",
                    "data": None,
                },
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, production: bool = False) -> None:
        super().__init__(app)
        self.production = production

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src 'self' blob:"
        )
        if self.production and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class RequestIdMiddleware(BaseHTTPMiddleware):
    _valid = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if self._valid.fullmatch(supplied) else uuid4().hex
        request.state.request_id = request_id
        context_token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(context_token)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            metrics_registry.record_request(perf_counter() - started, True)
            raise
        metrics_registry.record_request(perf_counter() - started, response.status_code >= 500)
        response.headers["X-Process-Time-Ms"] = f"{(perf_counter() - started) * 1000:.2f}"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, limit_per_minute: int) -> None:
        super().__init__(app)
        self.limit = limit_per_minute
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in {"/api/v1/health", "/api/v1/metrics"}:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        now = time()
        with self.lock:
            bucket = self.requests[client]
            while bucket and bucket[0] <= now - 60:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return JSONResponse(
                    status_code=429,
                    content={"code": 42900, "message": "请求过于频繁，请稍后重试", "data": None},
                )
            bucket.append(now)
        return await call_next(request)

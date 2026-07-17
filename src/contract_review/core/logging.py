from __future__ import annotations

import logging
import re
from contextvars import ContextVar, Token

_request_id: ContextVar[str] = ContextVar("request_id", default="-")
_secret_patterns = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(
        r"(?i)(\b(?:api[_-]?key|authorization|password|secret|token)\b\s*[:=]\s*)"
        r"(?:Bearer\s+)?(?:['\"]?)[^\s,;}&]+"
    ),
)


def set_request_id(value: str) -> Token[str]:
    return _request_id.set(value)


def reset_request_id(token: Token[str]) -> None:
    _request_id.reset(token)


def redact_log_message(message: str) -> str:
    redacted = _secret_patterns[1].sub(r"\1[REDACTED]", message)
    return _secret_patterns[0].sub("Bearer [REDACTED]", redacted)


class SecurityContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        record.msg = redact_log_message(record.getMessage())
        record.args = ()
        return True


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] [request_id=%(request_id)s] %(message)s",
    )
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in root.handlers:
        if not any(isinstance(item, SecurityContextFilter) for item in handler.filters):
            handler.addFilter(SecurityContextFilter())

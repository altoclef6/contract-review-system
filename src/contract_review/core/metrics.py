from __future__ import annotations

import threading
from dataclasses import dataclass, field
from time import perf_counter


@dataclass
class MetricsRegistry:
    started_at: float = field(default_factory=perf_counter)
    requests_total: int = 0
    errors_total: int = 0
    request_duration_total: float = 0
    ai_calls_total: int = 0
    ai_errors_total: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_request(self, duration: float, is_error: bool) -> None:
        with self._lock:
            self.requests_total += 1
            self.request_duration_total += duration
            self.errors_total += int(is_error)

    def record_ai_call(self, is_error: bool = False) -> None:
        with self._lock:
            self.ai_calls_total += 1
            self.ai_errors_total += int(is_error)

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            average = (
                self.request_duration_total / self.requests_total if self.requests_total else 0
            )
            error_rate = self.errors_total / self.requests_total if self.requests_total else 0
            return {
                "requests_total": self.requests_total,
                "errors_total": self.errors_total,
                "error_rate": round(error_rate, 4),
                "average_request_ms": round(average * 1000, 2),
                "ai_calls_total": self.ai_calls_total,
                "ai_errors_total": self.ai_errors_total,
                "uptime_seconds": round(perf_counter() - self.started_at, 2),
            }


metrics_registry = MetricsRegistry()

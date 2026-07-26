from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any


class LocalTaskExecutor:
    """Retain, bound, and cleanly cancel desktop background work."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()
        self._semaphore: asyncio.Semaphore | None = None
        self._limit: int | None = None

    def submit(self, work: Awaitable[Any], *, max_concurrent: int) -> None:
        if self._semaphore is None or self._limit != max_concurrent:
            self._semaphore = asyncio.Semaphore(max_concurrent)
            self._limit = max_concurrent

        async def run() -> None:
            assert self._semaphore is not None
            async with self._semaphore:
                await work

        task = asyncio.create_task(run(), name="desktop-review-task")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self) -> None:
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()


local_task_executor = LocalTaskExecutor()

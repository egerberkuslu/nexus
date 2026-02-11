from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional


class StopTaskManager:
    """
    Deduplicate and track long-running "stop emulation" operations.

    Some stop flows can take long enough to hit HTTP/proxy timeouts, so the API
    kicks off background tasks and provides idempotency via this manager.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        key: str,
        coro_factory: Callable[[], Awaitable[object]],
        *,
        task_name: Optional[str] = None,
    ) -> asyncio.Task:
        async with self._lock:
            existing = self._tasks.get(key)
            if existing is not None and not existing.done():
                return existing

            task_ref: asyncio.Task | None = None

            async def _runner() -> object:
                try:
                    return await coro_factory()
                finally:
                    async with self._lock:
                        if task_ref is not None and self._tasks.get(key) is task_ref:
                            self._tasks.pop(key, None)

            task_ref = asyncio.create_task(_runner(), name=task_name)
            self._tasks[key] = task_ref
            return task_ref

    def is_running(self, key: Optional[str]) -> bool:
        if not key:
            return False
        task = self._tasks.get(key)
        return task is not None and not task.done()


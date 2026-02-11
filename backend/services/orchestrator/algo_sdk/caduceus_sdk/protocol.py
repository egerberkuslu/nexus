from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class WaitRequest:
    timeout_seconds: float = 0.0


class Mailbox:
    def __init__(self) -> None:
        self._queue: list[dict[str, Any]] = []

    def put(self, message: dict[str, Any]) -> None:
        self._queue.append(message)

    def get(self, timeout_seconds: float = 0.0) -> WaitRequest:
        return WaitRequest(timeout_seconds=float(timeout_seconds or 0.0))

    def pop(self) -> Optional[dict[str, Any]]:
        if not self._queue:
            return None
        return self._queue.pop(0)

    def __len__(self) -> int:
        return len(self._queue)


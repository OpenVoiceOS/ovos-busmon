"""Capture ring buffer for bus messages."""
from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Iterator, List, Optional


@dataclass
class CapturedMessage:
    id: int
    timestamp: str
    msg_type: str
    data: dict
    context: dict
    session: Optional[str] = None
    source: Optional[str] = None
    destination: Optional[str] = None
    session_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "type": self.msg_type,
            "session": self.session,
            "session_data": self.session_data,
            "source": self.source,
            "destination": self.destination,
            "context": self.context,
            "data": self.data,
        }

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict())


class RingBuffer:
    """Fixed-capacity deque of CapturedMessage with monotonic IDs."""

    def __init__(self, maxlen: int = 2000) -> None:
        self._maxlen = maxlen
        self._buf: deque[CapturedMessage] = deque(maxlen=maxlen)
        self._counter: int = 0

    @property
    def maxlen(self) -> int:
        return self._maxlen

    def append(self, msg: CapturedMessage) -> None:
        self._buf.append(msg)

    def next_id(self) -> int:
        self._counter += 1
        return self._counter

    def since(self, since_id: int = 0, limit: Optional[int] = None) -> List[CapturedMessage]:
        """Return messages with id > since_id, newest-last order, up to *limit*."""
        result = [m for m in self._buf if m.id > since_id]
        if limit is not None:
            result = result[-limit:]
        return result

    def all(self) -> List[CapturedMessage]:
        return list(self._buf)

    def export_jsonl(self) -> str:
        return "\n".join(m.to_jsonl_line() for m in self._buf)

    def clear(self) -> None:
        self._buf.clear()

    def __len__(self) -> int:
        return len(self._buf)

    def __iter__(self) -> Iterator[CapturedMessage]:
        return iter(self._buf)

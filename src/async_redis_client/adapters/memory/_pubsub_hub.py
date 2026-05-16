from __future__ import annotations

import asyncio
import fnmatch
import queue
import threading
from collections import defaultdict

from async_redis_client.adapters.redis._pubsub_helpers import (
    full_channel,
    logical_channel,
)
from async_redis_client.schemas import PubSubMessage


class MemoryPubSubHub:
    """In-process fan-out for memory pub/sub adapters (thread-safe)."""

    def __init__(self, *, channel_prefix: str = "") -> None:
        self._channel_prefix = channel_prefix
        self._lock = threading.Lock()
        self._channel_queues: dict[str, list[queue.Queue[PubSubMessage | None]]] = (
            defaultdict(list)
        )
        self._pattern_queues: list[tuple[str, queue.Queue[PubSubMessage | None]]] = []

    def _physical(self, channel: str) -> str:
        return full_channel(self._channel_prefix, channel)

    def register_channel(self, channel: str) -> queue.Queue[PubSubMessage | None]:
        physical = self._physical(channel)
        q: queue.Queue[PubSubMessage | None] = queue.Queue()
        with self._lock:
            self._channel_queues[physical].append(q)
        return q

    def register_pattern(self, pattern: str) -> queue.Queue[PubSubMessage | None]:
        physical = self._physical(pattern)
        q: queue.Queue[PubSubMessage | None] = queue.Queue()
        with self._lock:
            self._pattern_queues.append((physical, q))
        return q

    def unregister_queue(self, q: queue.Queue[PubSubMessage | None]) -> None:
        with self._lock:
            for physical, subs in list(self._channel_queues.items()):
                if q in subs:
                    subs.remove(q)
                    if not subs:
                        del self._channel_queues[physical]
            self._pattern_queues = [
                (p, qq) for p, qq in self._pattern_queues if qq is not q
            ]

    def publish(self, channel: str, message: str | bytes) -> int:
        physical = self._physical(channel)
        logical = logical_channel(self._channel_prefix, physical)
        payload = PubSubMessage(channel=logical, data=message)
        delivered = 0
        with self._lock:
            targets = list(self._channel_queues.get(physical, []))
            pattern_items = list(self._pattern_queues)
        for q in targets:
            q.put(payload)
            delivered += 1
        for pattern, q in pattern_items:
            if fnmatch.fnmatch(physical, pattern):
                logical_pattern = logical_channel(self._channel_prefix, pattern)
                q.put(
                    PubSubMessage(
                        channel=logical,
                        data=message,
                        pattern=logical_pattern,
                    )
                )
                delivered += 1
        return delivered


class AsyncMemoryPubSubHub:
    """In-process fan-out for async memory pub/sub adapters."""

    def __init__(self, *, channel_prefix: str = "") -> None:
        self._channel_prefix = channel_prefix
        self._channel_queues: dict[str, list[asyncio.Queue[PubSubMessage | None]]] = (
            defaultdict(list)
        )
        self._pattern_queues: list[tuple[str, asyncio.Queue[PubSubMessage | None]]] = []

    def _physical(self, channel: str) -> str:
        return full_channel(self._channel_prefix, channel)

    def register_channel(self, channel: str) -> asyncio.Queue[PubSubMessage | None]:
        physical = self._physical(channel)
        q: asyncio.Queue[PubSubMessage | None] = asyncio.Queue()
        self._channel_queues[physical].append(q)
        return q

    def register_pattern(self, pattern: str) -> asyncio.Queue[PubSubMessage | None]:
        physical = self._physical(pattern)
        q: asyncio.Queue[PubSubMessage | None] = asyncio.Queue()
        self._pattern_queues.append((physical, q))
        return q

    def unregister_queue(self, q: asyncio.Queue[PubSubMessage | None]) -> None:
        for physical, subs in list(self._channel_queues.items()):
            if q in subs:
                subs.remove(q)
                if not subs:
                    del self._channel_queues[physical]
        self._pattern_queues = [
            (p, qq) for p, qq in self._pattern_queues if qq is not q
        ]

    async def publish(self, channel: str, message: str | bytes) -> int:
        physical = self._physical(channel)
        logical = logical_channel(self._channel_prefix, physical)
        delivered = 0
        for q in self._channel_queues.get(physical, []):
            await q.put(PubSubMessage(channel=logical, data=message))
            delivered += 1
        for pattern, q in self._pattern_queues:
            if fnmatch.fnmatch(physical, pattern):
                logical_pattern = logical_channel(self._channel_prefix, pattern)
                await q.put(
                    PubSubMessage(
                        channel=logical,
                        data=message,
                        pattern=logical_pattern,
                    )
                )
                delivered += 1
        return delivered

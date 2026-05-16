from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Self

from async_redis_client.adapters.memory._pubsub_hub import AsyncMemoryPubSubHub
from async_redis_client.errors import PubSubClosedError
from async_redis_client.schemas import PubSubMessage


class MemoryPubSubSubscriptionAsyncAdapter:
    __slots__ = ("_hub", "_queue", "_closed")

    def __init__(
        self,
        hub: AsyncMemoryPubSubHub,
        q: asyncio.Queue[PubSubMessage | None],
    ) -> None:
        self._hub = hub
        self._queue = q
        self._closed = False

    def _require_open(self) -> None:
        if self._closed:
            raise PubSubClosedError("Memory pub/sub subscription is closed")

    async def unsubscribe(self, *channels: str) -> None:
        self._require_open()
        if not channels:
            await self.close()

    async def punsubscribe(self, *patterns: str) -> None:
        self._require_open()
        if not patterns:
            await self.close()

    async def get_message(self, timeout: float | None = 1.0) -> PubSubMessage | None:
        self._require_open()
        try:
            if timeout is None:
                return await self._queue.get()
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def listen(self) -> AsyncIterator[PubSubMessage]:
        self._require_open()
        while True:
            msg = await self.get_message(timeout=None)
            if msg is None:
                break
            yield msg

    async def close(self) -> None:
        if self._closed:
            return
        self._hub.unregister_queue(self._queue)
        self._closed = True


class MemoryPubSubAsyncAdapter:
    """
    In-memory :class:`~async_redis_client.ports.async_pubsub_port.PubSubAsyncPort` for unit tests.

    Each ``subscribe`` / ``psubscribe`` accepts **one** channel or pattern (Redis allows many).
    The hub is not thread-safe; use one event loop / task set per adapter instance.
    """

    __slots__ = ("_hub", "_closed")

    def __init__(self, *, channel_prefix: str = "") -> None:
        self._hub = AsyncMemoryPubSubHub(channel_prefix=channel_prefix)
        self._closed = False

    async def close(self) -> None:
        self._closed = True

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    def _require_open(self) -> None:
        if self._closed:
            raise PubSubClosedError("Memory pub/sub adapter is closed")

    async def publish(self, channel: str, message: str | bytes) -> int:
        self._require_open()
        return await self._hub.publish(channel, message)

    async def subscribe(self, *channels: str) -> MemoryPubSubSubscriptionAsyncAdapter:
        self._require_open()
        if len(channels) != 1:
            raise ValueError("Memory adapter supports one channel per subscription")
        q = self._hub.register_channel(channels[0])
        return MemoryPubSubSubscriptionAsyncAdapter(self._hub, q)

    async def psubscribe(self, *patterns: str) -> MemoryPubSubSubscriptionAsyncAdapter:
        self._require_open()
        if len(patterns) != 1:
            raise ValueError("Memory adapter supports one pattern per subscription")
        q = self._hub.register_pattern(patterns[0])
        return MemoryPubSubSubscriptionAsyncAdapter(self._hub, q)

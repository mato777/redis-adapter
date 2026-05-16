from __future__ import annotations

import queue
from collections.abc import Iterator
from typing import Self

from async_redis_client.adapters.memory._pubsub_hub import MemoryPubSubHub
from async_redis_client.errors import PubSubClosedError
from async_redis_client.schemas import PubSubMessage


class MemoryPubSubSubscriptionSyncAdapter:
    __slots__ = ("_hub", "_queue", "_closed")

    def __init__(
        self, hub: MemoryPubSubHub, q: queue.Queue[PubSubMessage | None]
    ) -> None:
        self._hub = hub
        self._queue = q
        self._closed = False

    def _require_open(self) -> None:
        if self._closed:
            raise PubSubClosedError("Memory pub/sub subscription is closed")

    def unsubscribe(self, *channels: str) -> None:
        self._require_open()
        if not channels:
            self.close()

    def punsubscribe(self, *patterns: str) -> None:
        self._require_open()
        if not patterns:
            self.close()

    def get_message(self, timeout: float | None = 1.0) -> PubSubMessage | None:
        self._require_open()
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def listen(self) -> Iterator[PubSubMessage]:
        self._require_open()
        while True:
            msg = self.get_message(timeout=None)
            if msg is None:
                break
            yield msg

    def close(self) -> None:
        if self._closed:
            return
        self._hub.unregister_queue(self._queue)
        self._closed = True


class MemoryPubSubSyncAdapter:
    """
    In-memory :class:`~async_redis_client.ports.sync_pubsub_port.PubSubSyncPort` for unit tests.

    Fan-out is process-local; there is no network or Redis semantics beyond channel names.
    Unlike Redis, each ``subscribe`` / ``psubscribe`` accepts **one** channel or pattern only.
    """

    __slots__ = ("_hub", "_closed")

    def __init__(self, *, channel_prefix: str = "") -> None:
        self._hub = MemoryPubSubHub(channel_prefix=channel_prefix)
        self._closed = False

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _require_open(self) -> None:
        if self._closed:
            raise PubSubClosedError("Memory pub/sub adapter is closed")

    def publish(self, channel: str, message: str | bytes) -> int:
        self._require_open()
        return self._hub.publish(channel, message)

    def subscribe(self, *channels: str) -> MemoryPubSubSubscriptionSyncAdapter:
        self._require_open()
        if len(channels) != 1:
            raise ValueError("Memory adapter supports one channel per subscription")
        q = self._hub.register_channel(channels[0])
        return MemoryPubSubSubscriptionSyncAdapter(self._hub, q)

    def psubscribe(self, *patterns: str) -> MemoryPubSubSubscriptionSyncAdapter:
        self._require_open()
        if len(patterns) != 1:
            raise ValueError("Memory adapter supports one pattern per subscription")
        q = self._hub.register_pattern(patterns[0])
        return MemoryPubSubSubscriptionSyncAdapter(self._hub, q)

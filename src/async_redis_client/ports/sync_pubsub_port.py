from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from async_redis_client.pubsub_message import PubSubMessage


class PubSubSubscriptionSyncPort(Protocol):
    """Active channel or pattern subscription (blocking receive APIs)."""

    def unsubscribe(self, *channels: str) -> None: ...

    def punsubscribe(self, *patterns: str) -> None: ...

    def get_message(self, timeout: float | None = 1.0) -> PubSubMessage | None: ...

    def listen(self) -> Iterator[PubSubMessage]: ...

    def close(self) -> None: ...


class PubSubSyncPort(Protocol):
    """Sync Redis-style publish/subscribe contract."""

    def publish(self, channel: str, message: str | bytes) -> int: ...

    def subscribe(self, *channels: str) -> PubSubSubscriptionSyncPort: ...

    def psubscribe(self, *patterns: str) -> PubSubSubscriptionSyncPort: ...

    def close(self) -> None: ...

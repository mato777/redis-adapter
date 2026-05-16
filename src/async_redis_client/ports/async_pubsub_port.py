from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from async_redis_client.schemas import PubSubMessage


class PubSubSubscriptionAsyncPort(Protocol):
    """Active channel or pattern subscription (async receive APIs)."""

    async def unsubscribe(self, *channels: str) -> None: ...

    async def punsubscribe(self, *patterns: str) -> None: ...

    async def get_message(
        self, timeout: float | None = 1.0
    ) -> PubSubMessage | None: ...

    def listen(self) -> AsyncIterator[PubSubMessage]: ...

    async def close(self) -> None: ...


class PubSubAsyncPort(Protocol):
    """Async Redis-style publish/subscribe contract."""

    async def publish(self, channel: str, message: str | bytes) -> int: ...

    async def subscribe(self, *channels: str) -> PubSubSubscriptionAsyncPort: ...

    async def psubscribe(self, *patterns: str) -> PubSubSubscriptionAsyncPort: ...

    async def close(self) -> None: ...

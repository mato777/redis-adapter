from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Self

from redis.asyncio import Redis as AsyncRedis
from redis.asyncio.client import PubSub as AsyncPubSub
from redis.asyncio.cluster import RedisCluster as AsyncRedisCluster

from async_redis_client.adapters.redis._pubsub_helpers import (
    full_channel,
    parse_pubsub_message,
)
from async_redis_client.errors import PubSubClosedError
from async_redis_client.schemas import PubSubMessage

RedisAsyncClient = AsyncRedis | AsyncRedisCluster


class RedisPubSubSubscriptionAsyncAdapter:
    """Async subscription handle returned by :meth:`RedisPubSubAsyncAdapter.subscribe`."""

    __slots__ = ("_pubsub", "_channel_prefix", "_closed")

    def __init__(self, pubsub: AsyncPubSub, *, channel_prefix: str = "") -> None:
        self._pubsub = pubsub
        self._channel_prefix = channel_prefix
        self._closed = False

    def _require_open(self) -> None:
        if self._closed:
            raise PubSubClosedError("Redis pub/sub subscription is closed")

    async def unsubscribe(self, *channels: str) -> None:
        self._require_open()
        if channels:
            physical = [full_channel(self._channel_prefix, c) for c in channels]
            await self._pubsub.unsubscribe(*physical)
        else:
            await self._pubsub.unsubscribe()

    async def punsubscribe(self, *patterns: str) -> None:
        self._require_open()
        if patterns:
            physical = [full_channel(self._channel_prefix, p) for p in patterns]
            await self._pubsub.punsubscribe(*physical)
        else:
            await self._pubsub.punsubscribe()

    async def get_message(self, timeout: float | None = 1.0) -> PubSubMessage | None:
        self._require_open()
        deadline = time.monotonic() + timeout if timeout is not None else None
        while True:
            remaining = (
                None if deadline is None else max(0.0, deadline - time.monotonic())
            )
            if deadline is not None and remaining == 0.0:
                return None
            raw = await self._pubsub.get_message(
                ignore_subscribe_messages=False,
                timeout=remaining,
            )
            if raw is None:
                return None
            msg = parse_pubsub_message(raw, channel_prefix=self._channel_prefix)
            if msg is not None:
                return msg

    async def listen(self) -> AsyncIterator[PubSubMessage]:
        self._require_open()
        async for raw in self._pubsub.listen():
            msg = parse_pubsub_message(raw, channel_prefix=self._channel_prefix)
            if msg is not None:
                yield msg

    async def close(self) -> None:
        if self._closed:
            return
        await self._pubsub.aclose()
        self._closed = True


class RedisPubSubAsyncAdapter:
    """
    Async Redis pub/sub implementing :class:`~async_redis_client.ports.async_pubsub_port.PubSubAsyncPort`.

    **Lifecycle:** URL factories set ``owns_client=True``; use ``async with adapter:`` or await
    :meth:`close`. :meth:`aclose` is an alias of :meth:`close`. Close each subscription before
    closing this adapter; open subscriptions are not tracked automatically.
    """

    __slots__ = ("_client", "_channel_prefix", "_owns_client", "_closed")

    def __init__(
        self,
        client: RedisAsyncClient,
        *,
        channel_prefix: str = "",
        owns_client: bool = False,
    ) -> None:
        self._client = client
        self._channel_prefix = channel_prefix
        self._owns_client = owns_client
        self._closed = False

    @classmethod
    def from_standalone_url(
        cls,
        url: str,
        *,
        channel_prefix: str = "",
        **kwargs: object,
    ) -> RedisPubSubAsyncAdapter:
        client = AsyncRedis.from_url(url, **kwargs)  # type: ignore[arg-type]
        return cls(client, channel_prefix=channel_prefix, owns_client=True)

    @classmethod
    def from_cluster_url(
        cls,
        url: str,
        *,
        channel_prefix: str = "",
        **kwargs: object,
    ) -> RedisPubSubAsyncAdapter:
        client = AsyncRedisCluster.from_url(url, **kwargs)  # type: ignore[arg-type]
        return cls(client, channel_prefix=channel_prefix, owns_client=True)

    async def close(self) -> None:
        if self._closed:
            return
        if self._owns_client:
            await self._client.aclose()
            self._owns_client = False
        self._closed = True

    aclose = close

    async def __aenter__(self) -> Self:
        self._require_open()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    def _require_open(self) -> None:
        if self._closed:
            raise PubSubClosedError("Redis pub/sub adapter is closed")

    async def publish(self, channel: str, message: str | bytes) -> int:
        self._require_open()
        return int(
            await self._client.publish(
                full_channel(self._channel_prefix, channel), message
            )
        )

    async def subscribe(self, *channels: str) -> RedisPubSubSubscriptionAsyncAdapter:
        self._require_open()
        pubsub = self._client.pubsub()
        physical = [full_channel(self._channel_prefix, c) for c in channels]
        await pubsub.subscribe(*physical)
        return RedisPubSubSubscriptionAsyncAdapter(
            pubsub, channel_prefix=self._channel_prefix
        )

    async def psubscribe(self, *patterns: str) -> RedisPubSubSubscriptionAsyncAdapter:
        self._require_open()
        pubsub = self._client.pubsub()
        physical = [full_channel(self._channel_prefix, p) for p in patterns]
        await pubsub.psubscribe(*physical)
        return RedisPubSubSubscriptionAsyncAdapter(
            pubsub, channel_prefix=self._channel_prefix
        )

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Self

from redis import Redis
from redis.client import PubSub
from redis.cluster import RedisCluster

from async_redis_client.adapters.redis._pubsub_helpers import (
    full_channel,
    parse_pubsub_message,
)
from async_redis_client.errors import PubSubClosedError
from async_redis_client.pubsub_message import PubSubMessage

RedisSyncClient = Redis | RedisCluster


class RedisPubSubSubscriptionSyncAdapter:
    """Sync subscription handle returned by :meth:`RedisPubSubSyncAdapter.subscribe`."""

    __slots__ = ("_pubsub", "_channel_prefix", "_closed")

    def __init__(self, pubsub: PubSub, *, channel_prefix: str = "") -> None:
        self._pubsub = pubsub
        self._channel_prefix = channel_prefix
        self._closed = False

    def _require_open(self) -> None:
        if self._closed:
            raise PubSubClosedError("Redis pub/sub subscription is closed")

    def unsubscribe(self, *channels: str) -> None:
        self._require_open()
        if channels:
            physical = [full_channel(self._channel_prefix, c) for c in channels]
            self._pubsub.unsubscribe(*physical)
        else:
            self._pubsub.unsubscribe()

    def punsubscribe(self, *patterns: str) -> None:
        self._require_open()
        if patterns:
            physical = [full_channel(self._channel_prefix, p) for p in patterns]
            self._pubsub.punsubscribe(*physical)
        else:
            self._pubsub.punsubscribe()

    def get_message(self, timeout: float | None = 1.0) -> PubSubMessage | None:
        self._require_open()
        deadline = time.monotonic() + timeout if timeout is not None else None
        while True:
            remaining = (
                None if deadline is None else max(0.0, deadline - time.monotonic())
            )
            if deadline is not None and remaining == 0.0:
                return None
            raw = self._pubsub.get_message(
                ignore_subscribe_messages=False,
                timeout=remaining,
            )
            if raw is None:
                return None
            msg = parse_pubsub_message(raw, channel_prefix=self._channel_prefix)
            if msg is not None:
                return msg

    def listen(self) -> Iterator[PubSubMessage]:
        self._require_open()
        for raw in self._pubsub.listen():
            msg = parse_pubsub_message(raw, channel_prefix=self._channel_prefix)
            if msg is not None:
                yield msg

    def close(self) -> None:
        if self._closed:
            return
        self._pubsub.close()
        self._closed = True


class RedisPubSubSyncAdapter:
    """
    Sync Redis pub/sub implementing :class:`~async_redis_client.ports.sync_pubsub_port.PubSubSyncPort`.

    **Publish** uses the injected :class:`~redis.Redis` client. **Subscribe** / **psubscribe** open a
    dedicated :class:`~redis.client.PubSub` connection; close each subscription when finished.

    **Lifecycle:** URL factories set ``owns_client=True``; use ``with adapter:`` or :meth:`close`.
    """

    __slots__ = ("_client", "_channel_prefix", "_owns_client", "_closed")

    def __init__(
        self,
        client: RedisSyncClient,
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
    ) -> RedisPubSubSyncAdapter:
        client = Redis.from_url(url, **kwargs)  # type: ignore[arg-type]
        return cls(client, channel_prefix=channel_prefix, owns_client=True)

    @classmethod
    def from_cluster_url(
        cls,
        url: str,
        *,
        channel_prefix: str = "",
        **kwargs: object,
    ) -> RedisPubSubSyncAdapter:
        client = RedisCluster.from_url(url, **kwargs)  # type: ignore[arg-type]
        return cls(client, channel_prefix=channel_prefix, owns_client=True)

    def close(self) -> None:
        if self._closed:
            return
        if self._owns_client:
            self._client.close()
            self._owns_client = False
        self._closed = True

    def __enter__(self) -> Self:
        self._require_open()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _require_open(self) -> None:
        if self._closed:
            raise PubSubClosedError("Redis pub/sub adapter is closed")

    def publish(self, channel: str, message: str | bytes) -> int:
        self._require_open()
        return int(
            self._client.publish(full_channel(self._channel_prefix, channel), message)
        )

    def subscribe(self, *channels: str) -> RedisPubSubSubscriptionSyncAdapter:
        self._require_open()
        pubsub = self._client.pubsub()
        physical = [full_channel(self._channel_prefix, c) for c in channels]
        pubsub.subscribe(*physical)
        return RedisPubSubSubscriptionSyncAdapter(
            pubsub, channel_prefix=self._channel_prefix
        )

    def psubscribe(self, *patterns: str) -> RedisPubSubSubscriptionSyncAdapter:
        self._require_open()
        pubsub = self._client.pubsub()
        physical = [full_channel(self._channel_prefix, p) for p in patterns]
        pubsub.psubscribe(*physical)
        return RedisPubSubSubscriptionSyncAdapter(
            pubsub, channel_prefix=self._channel_prefix
        )

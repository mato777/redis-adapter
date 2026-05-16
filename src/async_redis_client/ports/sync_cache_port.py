from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, TypeVar

from pydantic import BaseModel, JsonValue

TModel = TypeVar("TModel")


class CacheSyncPort(Protocol):
    """Synchronous cache contract for application code (no Redis imports)."""

    def close(self) -> None:
        """
        Release resources held by the implementation.

        For Redis adapters built with :meth:`~async_redis_client.adapters.redis.sync_adapter.RedisCacheSyncAdapter.from_standalone_url`
        or :meth:`~async_redis_client.adapters.redis.sync_adapter.RedisCacheSyncAdapter.from_cluster_url`
        (``owns_client=True``), this closes the underlying client. When the client was injected with
        ``owns_client=False``, callers remain responsible for closing the Redis client.

        Further cache operations after an owned adapter is closed raise
        :exc:`~async_redis_client.errors.CacheClosedError`.
        """

    def get(self, key: str) -> JsonValue | None:
        """Decrypt and return a JSON value, or ``None`` if missing."""

    def get_or_raise_if_missing(self, key: str) -> JsonValue:
        """
        Like :meth:`get`, but raises :exc:`~async_redis_client.errors.CacheKeyNotFoundError`
        when there is **no stored JSON blob** for ``key``.

        JSON ``null`` (decoded as Python ``None``) still counts as present — only an absent key
        raises.
        """

    def set(self, key: str, value: JsonValue, ttl_seconds: int | None = None) -> None:
        """Encrypt Pydantic-validated JSON bytes and store."""

    def set_json(
        self, key: str, value: JsonValue, ttl_seconds: int | None = None
    ) -> None:
        """Alias of :meth:`set` for clarity at call sites."""

    def get_json(self, key: str) -> JsonValue | None:
        """Alias of :meth:`get`."""

    def get_json_or_raise_if_missing(self, key: str) -> JsonValue:
        """Alias of :meth:`get_or_raise_if_missing`."""

    def set_model(
        self, key: str, model: BaseModel, ttl_seconds: int | None = None
    ) -> None:
        """Serialize ``BaseModel`` to JSON bytes, encrypt, and store."""

    def get_as_model(self, key: str, model_type: type[TModel]) -> TModel | None:
        """Decrypt and validate JSON into ``model_type``."""

    def delete(self, key: str) -> int:
        """Delete key; returns Redis-style deletion count."""

    def exists(self, key: str) -> bool: ...

    def incr(self, key: str, amount: int = 1) -> int:
        """Atomic increment on a plaintext integer key (not encrypted)."""

    def decr(self, key: str, amount: int = 1) -> int:
        """Atomic decrement on a plaintext integer key (not encrypted)."""

    def incrby(self, key: str, amount: int) -> int: ...

    def set_many(
        self, mapping: Mapping[str, JsonValue], ttl_seconds: int | None = None
    ) -> None:
        """
        Batch encrypted JSON writes.

        On Redis Cluster, all logical keys must map to the **same hash slot**
        (use hash tags in keys or ``key_prefix``, e.g. ``{tenant}:a``).
        """

    def get_many(self, keys: Sequence[str]) -> dict[str, JsonValue | None]:
        """
        Batch decrypt + JSON reads.

        Cluster: keys must share one hash slot; otherwise CROSSSLOT errors apply.
        """

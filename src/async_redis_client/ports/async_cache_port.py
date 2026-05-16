from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, TypeVar

from pydantic import BaseModel, JsonValue

TModel = TypeVar("TModel")


class CacheAsyncPort(Protocol):
    """Async cache contract mirroring :class:`~async_redis_client.ports.sync_cache_port.CacheSyncPort`."""

    async def close(self) -> None:
        """
        Release resources held by the implementation.

        For Redis adapters from URL factory classmethods (``owns_client=True``), this closes the
        underlying asyncio client (via :meth:`~redis.asyncio.client.Redis.aclose`). When the client
        was injected with ``owns_client=False``, callers remain responsible for closing the Redis
        client.

        Further cache operations after an owned adapter is closed raise
        :exc:`~async_redis_client.errors.CacheClosedError`.
        """

    async def get(self, key: str) -> JsonValue | None: ...

    async def get_or_raise_if_missing(self, key: str) -> JsonValue: ...

    async def set(
        self, key: str, value: JsonValue, ttl_seconds: int | None = None
    ) -> None: ...

    async def set_json(
        self, key: str, value: JsonValue, ttl_seconds: int | None = None
    ) -> None: ...

    async def get_json(self, key: str) -> JsonValue | None: ...

    async def get_json_or_raise_if_missing(self, key: str) -> JsonValue: ...

    async def set_model(
        self, key: str, model: BaseModel, ttl_seconds: int | None = None
    ) -> None: ...

    async def get_as_model(
        self, key: str, model_type: type[TModel]
    ) -> TModel | None: ...

    async def delete(self, key: str) -> int: ...

    async def exists(self, key: str) -> bool: ...

    async def incr(self, key: str, amount: int = 1) -> int: ...

    async def decr(self, key: str, amount: int = 1) -> int: ...

    async def incrby(self, key: str, amount: int) -> int: ...

    async def set_many(
        self, mapping: Mapping[str, JsonValue], ttl_seconds: int | None = None
    ) -> None: ...

    async def get_many(self, keys: Sequence[str]) -> dict[str, JsonValue | None]: ...

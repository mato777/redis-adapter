from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Self, TypeVar

from pydantic import BaseModel, JsonValue

from async_redis_client.adapters.memory.sync_adapter import MemoryCacheSyncAdapter

TModel = TypeVar("TModel")


class MemoryCacheAsyncAdapter:
    """Async façade over :class:`MemoryCacheSyncAdapter` with an asyncio lock."""

    __slots__ = ("_inner", "_lock")

    def __init__(
        self,
        *,
        namespace: str = "",
        key_prefix: str = "",
    ) -> None:
        self._inner = MemoryCacheSyncAdapter(namespace=namespace, key_prefix=key_prefix)
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        """No-op; satisfies :class:`~async_redis_client.ports.async_cache_port.CacheAsyncPort`."""

    aclose = close

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close()

    async def get(self, key: str) -> JsonValue | None:
        async with self._lock:
            return self._inner.get(key)

    async def set(
        self, key: str, value: JsonValue, ttl_seconds: int | None = None
    ) -> None:
        async with self._lock:
            self._inner.set(key, value, ttl_seconds=ttl_seconds)

    async def set_json(
        self, key: str, value: JsonValue, ttl_seconds: int | None = None
    ) -> None:
        async with self._lock:
            self._inner.set_json(key, value, ttl_seconds=ttl_seconds)

    async def get_json(self, key: str) -> JsonValue | None:
        async with self._lock:
            return self._inner.get_json(key)

    async def get_or_raise_if_missing(self, key: str) -> JsonValue:
        async with self._lock:
            return self._inner.get_or_raise_if_missing(key)

    async def get_json_or_raise_if_missing(self, key: str) -> JsonValue:
        async with self._lock:
            return self._inner.get_json_or_raise_if_missing(key)

    async def set_model(
        self, key: str, model: BaseModel, ttl_seconds: int | None = None
    ) -> None:
        async with self._lock:
            self._inner.set_model(key, model, ttl_seconds=ttl_seconds)

    async def get_as_model(self, key: str, model_type: type[TModel]) -> TModel | None:
        async with self._lock:
            return self._inner.get_as_model(key, model_type)

    async def delete(self, key: str) -> int:
        async with self._lock:
            return self._inner.delete(key)

    async def exists(self, key: str) -> bool:
        async with self._lock:
            return self._inner.exists(key)

    async def incr(self, key: str, amount: int = 1) -> int:
        async with self._lock:
            return self._inner.incr(key, amount)

    async def decr(self, key: str, amount: int = 1) -> int:
        async with self._lock:
            return self._inner.decr(key, amount)

    async def incrby(self, key: str, amount: int) -> int:
        async with self._lock:
            return self._inner.incrby(key, amount)

    async def set_many(
        self, mapping: Mapping[str, JsonValue], ttl_seconds: int | None = None
    ) -> None:
        async with self._lock:
            self._inner.set_many(mapping, ttl_seconds=ttl_seconds)

    async def get_many(self, keys: Sequence[str]) -> dict[str, JsonValue | None]:
        async with self._lock:
            return self._inner.get_many(keys)

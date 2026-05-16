from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Self, TypeVar

from pydantic import BaseModel, JsonValue
from redis.asyncio import Redis as AsyncRedis
from redis.asyncio.cluster import RedisCluster as AsyncRedisCluster

from async_redis_client.adapters.redis._helpers import (
    decode_mget_json_rows,
    decrypt_json_tree,
    encrypt_json_tree,
    full_key,
    pipeline_enqueue_json_sets,
    redis_keys_from_logical,
    redis_raw_to_bytes,
)
from async_redis_client.crypto import (
    build_fernet,
    build_secondary_fernet,
    decrypt_bytes,
    encrypt_bytes,
)
from async_redis_client.errors import CacheClosedError, CacheKeyNotFoundError
from async_redis_client.serialization import dump_model, load_as_type

RedisAsyncClient = AsyncRedis | AsyncRedisCluster

TModel = TypeVar("TModel")


class RedisCacheAsyncAdapter:
    """
    Async Redis cache implementing :class:`~async_redis_client.ports.async_cache_port.CacheAsyncPort`.

    Semantics match :class:`~async_redis_client.adapters.redis.sync_adapter.RedisCacheSyncAdapter`:
    encrypted JSON/model payloads vs plaintext integer counters; Cluster hash-slot constraints
    apply to :meth:`set_many` / :meth:`get_many`. Secondary Fernet key behaves as in the sync adapter.

    **Lifecycle:** URL factories set ``owns_client=True``; use ``async with adapter:`` or await
    :meth:`close`. Injected clients default to ``owns_client=False`` (you close the Redis client),
    unless you pass ``owns_client=True``. :meth:`aclose` is an alias of :meth:`close`. After an
    owned shutdown, operations raise :exc:`~async_redis_client.errors.CacheClosedError`.
    """

    __slots__ = (
        "_client",
        "_fernet",
        "_fernet_secondary",
        "_namespace",
        "_key_prefix",
        "_owns_client",
        "_closed",
    )

    def __init__(
        self,
        client: RedisAsyncClient,
        *,
        fernet_key: bytes | None = None,
        fernet_key_secondary: bytes | None = None,
        namespace: str = "",
        key_prefix: str = "",
        owns_client: bool = False,
    ) -> None:
        self._client = client
        self._fernet = build_fernet(fernet_key=fernet_key)
        self._fernet_secondary = build_secondary_fernet(fernet_key=fernet_key_secondary)
        self._namespace = namespace
        self._key_prefix = key_prefix
        self._owns_client = owns_client
        self._closed = False

    @classmethod
    def from_standalone_url(
        cls,
        url: str,
        *,
        fernet_key: bytes | None = None,
        fernet_key_secondary: bytes | None = None,
        namespace: str = "",
        key_prefix: str = "",
        **kwargs: object,
    ) -> RedisCacheAsyncAdapter:
        client = AsyncRedis.from_url(url, **kwargs)  # type: ignore[arg-type]
        return cls(
            client,
            fernet_key=fernet_key,
            fernet_key_secondary=fernet_key_secondary,
            namespace=namespace,
            key_prefix=key_prefix,
            owns_client=True,
        )

    @classmethod
    def from_cluster_url(
        cls,
        url: str,
        *,
        fernet_key: bytes | None = None,
        fernet_key_secondary: bytes | None = None,
        namespace: str = "",
        key_prefix: str = "",
        **kwargs: object,
    ) -> RedisCacheAsyncAdapter:
        client = AsyncRedisCluster.from_url(url, **kwargs)  # type: ignore[arg-type]
        return cls(
            client,
            fernet_key=fernet_key,
            fernet_key_secondary=fernet_key_secondary,
            namespace=namespace,
            key_prefix=key_prefix,
            owns_client=True,
        )

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
            raise CacheClosedError("Redis cache adapter is closed")

    def _full_key(self, key: str) -> str:
        return full_key(self._namespace, self._key_prefix, key)

    async def get(self, key: str) -> JsonValue | None:
        self._require_open()
        raw = await self._client.get(self._full_key(key))
        if raw is None:
            return None
        data = redis_raw_to_bytes(raw)
        return decrypt_json_tree(self._fernet, data, secondary=self._fernet_secondary)

    async def set(
        self, key: str, value: JsonValue, ttl_seconds: int | None = None
    ) -> None:
        self._require_open()
        fk = self._full_key(key)
        blob = encrypt_json_tree(self._fernet, value)
        if ttl_seconds is not None:
            await self._client.set(fk, blob, ex=ttl_seconds)
        else:
            await self._client.set(fk, blob)

    async def set_json(
        self, key: str, value: JsonValue, ttl_seconds: int | None = None
    ) -> None:
        await self.set(key, value, ttl_seconds=ttl_seconds)

    async def get_json(self, key: str) -> JsonValue | None:
        return await self.get(key)

    async def get_or_raise_if_missing(self, key: str) -> JsonValue:
        self._require_open()
        raw = await self._client.get(self._full_key(key))
        if raw is None:
            raise CacheKeyNotFoundError(key)
        data = redis_raw_to_bytes(raw)
        return decrypt_json_tree(self._fernet, data, secondary=self._fernet_secondary)

    async def get_json_or_raise_if_missing(self, key: str) -> JsonValue:
        return await self.get_or_raise_if_missing(key)

    async def set_model(
        self, key: str, model: BaseModel, ttl_seconds: int | None = None
    ) -> None:
        self._require_open()
        fk = self._full_key(key)
        blob = encrypt_bytes(self._fernet, dump_model(model))
        if ttl_seconds is not None:
            await self._client.set(fk, blob, ex=ttl_seconds)
        else:
            await self._client.set(fk, blob)

    async def get_as_model(self, key: str, model_type: type[TModel]) -> TModel | None:
        self._require_open()
        raw = await self._client.get(self._full_key(key))
        if raw is None:
            return None
        data = redis_raw_to_bytes(raw)
        plain = decrypt_bytes(self._fernet, data, secondary=self._fernet_secondary)
        return load_as_type(model_type, plain)

    async def delete(self, key: str) -> int:
        self._require_open()
        return int(await self._client.delete(self._full_key(key)))

    async def exists(self, key: str) -> bool:
        self._require_open()
        return bool(await self._client.exists(self._full_key(key)))

    async def incr(self, key: str, amount: int = 1) -> int:
        self._require_open()
        return int(await self._client.incrby(self._full_key(key), amount))

    async def decr(self, key: str, amount: int = 1) -> int:
        self._require_open()
        return int(await self._client.decrby(self._full_key(key), amount))

    async def incrby(self, key: str, amount: int) -> int:
        self._require_open()
        return int(await self._client.incrby(self._full_key(key), amount))

    async def set_many(
        self, mapping: Mapping[str, JsonValue], ttl_seconds: int | None = None
    ) -> None:
        self._require_open()
        if not mapping:
            return
        pipe = self._client.pipeline(transaction=False)
        pipeline_enqueue_json_sets(
            pipe,
            mapping,
            namespace=self._namespace,
            key_prefix=self._key_prefix,
            fernet=self._fernet,
            ttl_seconds=ttl_seconds,
        )
        await pipe.execute()

    async def get_many(self, keys: Sequence[str]) -> dict[str, JsonValue | None]:
        self._require_open()
        if not keys:
            return {}
        rkeys = redis_keys_from_logical(self._namespace, self._key_prefix, keys)
        values = await self._client.mget(rkeys)
        return decode_mget_json_rows(
            keys,
            values,
            fernet=self._fernet,
            secondary=self._fernet_secondary,
        )

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Self, TypeVar

from pydantic import BaseModel, JsonValue
from redis import Redis
from redis.cluster import RedisCluster

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

RedisSyncClient = Redis | RedisCluster

TModel = TypeVar("TModel")


class RedisCacheSyncAdapter:
    """
    Redis-backed :class:`~async_redis_client.ports.sync_cache_port.CacheSyncPort`.

    Values at encrypted keys are Fernet ciphertext whose plaintext is UTF-8 JSON via Pydantic.
    Counter operations (:meth:`incr`, :meth:`decr`, :meth:`incrby`) store **plaintext** Redis
    integers — use a dedicated namespace (for example keys prefixed with ``counter:``) to avoid
    mixing them with encrypted blobs.

    Accepts either standalone :class:`~redis.Redis` or :class:`~redis.cluster.RedisCluster`.
    Multi-key helpers (:meth:`set_many`, :meth:`get_many`) must use keys in the **same hash slot**
    when using Cluster (prefer hash tags in ``namespace`` / ``key_prefix`` or logical keys).

    **Key rotation:** pass ``fernet_key_secondary`` (or set ``CACHE_FERNET_KEY_SECONDARY``) to
    decrypt legacy ciphertext; reads try the primary key first, then the secondary. Writes always
    use the primary key only.

    **Lifecycle:** URL factories set ``owns_client=True`` so :meth:`close` shuts down the client; use
    ``with adapter:`` or call :meth:`close` when using them. For an injected client, ``owns_client``
    defaults to ``False``—close the Redis client yourself, or pass ``owns_client=True`` if this
    adapter should own it. After an owned shutdown, further operations raise
    :exc:`~async_redis_client.errors.CacheClosedError`.
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
        client: RedisSyncClient,
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
    ) -> RedisCacheSyncAdapter:
        """Build a standalone :class:`~redis.Redis` client from ``url`` and wrap it."""
        client = Redis.from_url(url, **kwargs)  # type: ignore[arg-type]
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
    ) -> RedisCacheSyncAdapter:
        """Build :class:`~redis.cluster.RedisCluster` from ``url`` and wrap it."""
        client = RedisCluster.from_url(url, **kwargs)  # type: ignore[arg-type]
        return cls(
            client,
            fernet_key=fernet_key,
            fernet_key_secondary=fernet_key_secondary,
            namespace=namespace,
            key_prefix=key_prefix,
            owns_client=True,
        )

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
            raise CacheClosedError("Redis cache adapter is closed")

    def _full_key(self, key: str) -> str:
        return full_key(self._namespace, self._key_prefix, key)

    def get(self, key: str) -> JsonValue | None:
        self._require_open()
        raw = self._client.get(self._full_key(key))
        if raw is None:
            return None
        data = redis_raw_to_bytes(raw)
        return decrypt_json_tree(self._fernet, data, secondary=self._fernet_secondary)

    def set(self, key: str, value: JsonValue, ttl_seconds: int | None = None) -> None:
        self._require_open()
        fk = self._full_key(key)
        blob = encrypt_json_tree(self._fernet, value)
        if ttl_seconds is not None:
            self._client.set(fk, blob, ex=ttl_seconds)
        else:
            self._client.set(fk, blob)

    def set_json(
        self, key: str, value: JsonValue, ttl_seconds: int | None = None
    ) -> None:
        self.set(key, value, ttl_seconds=ttl_seconds)

    def get_json(self, key: str) -> JsonValue | None:
        return self.get(key)

    def get_or_raise_if_missing(self, key: str) -> JsonValue:
        self._require_open()
        raw = self._client.get(self._full_key(key))
        if raw is None:
            raise CacheKeyNotFoundError(key)
        data = redis_raw_to_bytes(raw)
        return decrypt_json_tree(self._fernet, data, secondary=self._fernet_secondary)

    def get_json_or_raise_if_missing(self, key: str) -> JsonValue:
        return self.get_or_raise_if_missing(key)

    def set_model(
        self, key: str, model: BaseModel, ttl_seconds: int | None = None
    ) -> None:
        self._require_open()
        fk = self._full_key(key)
        blob = encrypt_bytes(self._fernet, dump_model(model))
        if ttl_seconds is not None:
            self._client.set(fk, blob, ex=ttl_seconds)
        else:
            self._client.set(fk, blob)

    def get_as_model(self, key: str, model_type: type[TModel]) -> TModel | None:
        self._require_open()
        raw = self._client.get(self._full_key(key))
        if raw is None:
            return None
        data = redis_raw_to_bytes(raw)
        plain = decrypt_bytes(self._fernet, data, secondary=self._fernet_secondary)
        return load_as_type(model_type, plain)

    def delete(self, key: str) -> int:
        self._require_open()
        return int(self._client.delete(self._full_key(key)))

    def exists(self, key: str) -> bool:
        self._require_open()
        return bool(self._client.exists(self._full_key(key)))

    def incr(self, key: str, amount: int = 1) -> int:
        self._require_open()
        return int(self._client.incrby(self._full_key(key), amount))

    def decr(self, key: str, amount: int = 1) -> int:
        self._require_open()
        return int(self._client.decrby(self._full_key(key), amount))

    def incrby(self, key: str, amount: int) -> int:
        self._require_open()
        return int(self._client.incrby(self._full_key(key), amount))

    def set_many(
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
        pipe.execute()

    def get_many(self, keys: Sequence[str]) -> dict[str, JsonValue | None]:
        self._require_open()
        if not keys:
            return {}
        rkeys = redis_keys_from_logical(self._namespace, self._key_prefix, keys)
        values = self._client.mget(rkeys)
        return decode_mget_json_rows(
            keys,
            values,
            fernet=self._fernet,
            secondary=self._fernet_secondary,
        )

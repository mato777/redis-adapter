from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Self, TypeVar

from pydantic import BaseModel, JsonValue, TypeAdapter

from async_redis_client.errors import CacheKeyNotFoundError, SerializationError

TModel = TypeVar("TModel")


class MemoryCacheSyncAdapter:
    """
    Minimal in-memory implementation of :class:`~async_redis_client.ports.sync_cache_port.CacheSyncPort`.

    Intended for domain/unit tests without Redis. Mutually exclusive storage per key:
    JSON tree, ``BaseModel``, or integer counter (same collision rules as documented for Redis).
    TTL is not simulated (``ttl_seconds`` is accepted and ignored).

    Physical keys mirror Redis adapters: ``namespace + key_prefix +`` logical key passed to port methods.
    """

    __slots__ = ("_counters", "_json", "_models", "_namespace", "_key_prefix")

    def __init__(
        self,
        *,
        namespace: str = "",
        key_prefix: str = "",
    ) -> None:
        self._json: dict[str, JsonValue] = {}
        self._models: dict[str, BaseModel] = {}
        self._counters: dict[str, int] = {}
        self._namespace = namespace
        self._key_prefix = key_prefix

    def _full_key(self, logical_key: str) -> str:
        return f"{self._namespace}{self._key_prefix}{logical_key}"

    def close(self) -> None:
        """No-op; satisfies :class:`~async_redis_client.ports.sync_cache_port.CacheSyncPort`."""

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _clear_non_counter(self, physical_key: str) -> None:
        self._json.pop(physical_key, None)
        self._models.pop(physical_key, None)

    def get(self, key: str) -> JsonValue | None:
        fk = self._full_key(key)
        if fk in self._models:
            raise SerializationError("Key holds a model instance; use get_as_model().")
        if fk in self._counters:
            raise SerializationError("Key holds a counter; use incr/decr APIs.")
        return self._json.get(fk)

    def set(self, key: str, value: JsonValue, ttl_seconds: int | None = None) -> None:
        del ttl_seconds
        fk = self._full_key(key)
        self._clear_non_counter(fk)
        self._json[fk] = value

    def set_json(
        self, key: str, value: JsonValue, ttl_seconds: int | None = None
    ) -> None:
        self.set(key, value, ttl_seconds=ttl_seconds)

    def get_json(self, key: str) -> JsonValue | None:
        return self.get(key)

    def get_or_raise_if_missing(self, key: str) -> JsonValue:
        fk = self._full_key(key)
        if fk in self._models:
            raise SerializationError("Key holds a model instance; use get_as_model().")
        if fk in self._counters:
            raise SerializationError("Key holds a counter; use incr/decr APIs.")
        if fk not in self._json:
            raise CacheKeyNotFoundError(key)
        return self._json[fk]

    def get_json_or_raise_if_missing(self, key: str) -> JsonValue:
        return self.get_or_raise_if_missing(key)

    def set_model(
        self, key: str, model: BaseModel, ttl_seconds: int | None = None
    ) -> None:
        del ttl_seconds
        fk = self._full_key(key)
        self._clear_non_counter(fk)
        self._models[fk] = model
        self._json.pop(fk, None)

    def get_as_model(self, key: str, model_type: type[TModel]) -> TModel | None:
        fk = self._full_key(key)
        if fk in self._json:
            raw = TypeAdapter(JsonValue).dump_json(self._json[fk])
            return TypeAdapter(model_type).validate_json(raw)
        if fk in self._models:
            m = self._models[fk]
            if isinstance(m, model_type):
                return m
            return TypeAdapter(model_type).validate_python(m.model_dump())
        if fk in self._counters:
            raise SerializationError("Key holds a counter; cannot load as model.")
        return None

    def delete(self, key: str) -> int:
        fk = self._full_key(key)
        existed = fk in self._json or fk in self._models or fk in self._counters
        self._json.pop(fk, None)
        self._models.pop(fk, None)
        self._counters.pop(fk, None)
        return 1 if existed else 0

    def exists(self, key: str) -> bool:
        fk = self._full_key(key)
        return fk in self._json or fk in self._models or fk in self._counters

    def incr(self, key: str, amount: int = 1) -> int:
        fk = self._full_key(key)
        self._clear_non_counter(fk)
        cur = self._counters.get(fk, 0) + amount
        self._counters[fk] = cur
        return cur

    def decr(self, key: str, amount: int = 1) -> int:
        return self.incr(key, -amount)

    def incrby(self, key: str, amount: int) -> int:
        return self.incr(key, amount)

    def set_many(
        self, mapping: Mapping[str, JsonValue], ttl_seconds: int | None = None
    ) -> None:
        for k, v in mapping.items():
            self.set(k, v, ttl_seconds=ttl_seconds)

    def get_many(self, keys: Sequence[str]) -> dict[str, JsonValue | None]:
        return {k: self.get(k) for k in keys}

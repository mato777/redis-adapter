from __future__ import annotations

import pytest
from pydantic import BaseModel

from async_redis_client import MemoryCacheSyncAdapter, SerializationError


class SampleModel(BaseModel):
    label: str


class SampleModelAlias(BaseModel):
    label: str


def test_memory_sync_namespace_isolation() -> None:
    a = MemoryCacheSyncAdapter(namespace="a:")
    b = MemoryCacheSyncAdapter(namespace="b:", key_prefix="pre:")
    a.set_json("k", 1)
    b.set_json("k", 2)
    assert a.get_json("k") == 1
    assert b.get_json("k") == 2


def test_memory_sync_get_or_raise_errors_for_model_and_counter() -> None:
    mem = MemoryCacheSyncAdapter()
    mem.set_model("mod", SampleModel(label="x"))
    with pytest.raises(SerializationError, match="model instance"):
        mem.get_or_raise_if_missing("mod")

    mem.incr("counter")
    with pytest.raises(SerializationError, match="counter"):
        mem.get_or_raise_if_missing("counter")


def test_memory_sync_get_as_model_coercion_and_counter_error() -> None:
    mem = MemoryCacheSyncAdapter()
    mem.set_model("m", SampleModel(label="from-store"))
    loaded = mem.get_as_model("m", SampleModelAlias)
    assert isinstance(loaded, SampleModelAlias)
    assert loaded.label == "from-store"

    mem.incr("c")
    with pytest.raises(SerializationError, match="cannot load as model"):
        mem.get_as_model("c", SampleModel)

    assert mem.get_as_model("missing", SampleModel) is None


def test_memory_sync_model_and_json_paths() -> None:
    mem = MemoryCacheSyncAdapter()
    mem.set_model("m", SampleModel(label="a"))
    assert mem.get_as_model("m", SampleModel) == SampleModel(label="a")

    mem.set_json("raw", {"label": "from-json"})
    loaded = mem.get_as_model("raw", SampleModel)
    assert isinstance(loaded, SampleModel)
    assert loaded.label == "from-json"


def test_memory_sync_delete_exists_set_many() -> None:
    mem = MemoryCacheSyncAdapter()
    mem.set_many({"a": 1, "b": 2})
    assert mem.get_many(["a", "b", "z"]) == {"a": 1, "b": 2, "z": None}
    assert mem.exists("a") is True
    assert mem.delete("a") == 1
    assert mem.delete("a") == 0

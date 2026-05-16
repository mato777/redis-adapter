from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from async_redis_client import (
    CacheKeyNotFoundError,
    MemoryCacheAsyncAdapter,
    SerializationError,
)


class SampleModel(BaseModel):
    label: str


@pytest.fixture()
async def cache() -> MemoryCacheAsyncAdapter:
    return MemoryCacheAsyncAdapter()


@pytest.mark.asyncio
async def test_async_memory_namespace_isolation() -> None:
    a = MemoryCacheAsyncAdapter(namespace="a:")
    b = MemoryCacheAsyncAdapter(namespace="b:", key_prefix="pre:")
    await a.set_json("k", 1)
    await b.set_json("k", 2)
    assert await a.get_json("k") == 1
    assert await b.get_json("k") == 2


@pytest.mark.asyncio
async def test_async_memory_json_roundtrip(cache: MemoryCacheAsyncAdapter) -> None:
    await cache.set_json("k", {"ok": True})
    assert await cache.get_json("k") == {"ok": True}
    await cache.set("k2", [1], ttl_seconds=999)
    assert await cache.get("k2") == [1]


@pytest.mark.asyncio
async def test_async_memory_get_miss(cache: MemoryCacheAsyncAdapter) -> None:
    assert await cache.get("absent") is None


@pytest.mark.asyncio
async def test_async_memory_get_or_raise(cache: MemoryCacheAsyncAdapter) -> None:
    await cache.set_json("x", 1)
    assert await cache.get_or_raise_if_missing("x") == 1
    assert await cache.get_json_or_raise_if_missing("x") == 1
    with pytest.raises(CacheKeyNotFoundError):
        await cache.get_or_raise_if_missing("missing")


@pytest.mark.asyncio
async def test_async_memory_model_roundtrip(cache: MemoryCacheAsyncAdapter) -> None:
    await cache.set_model("m", SampleModel(label="a"))
    loaded = await cache.get_as_model("m", SampleModel)
    assert isinstance(loaded, SampleModel)
    assert loaded.label == "a"


@pytest.mark.asyncio
async def test_async_memory_get_as_model_from_json(
    cache: MemoryCacheAsyncAdapter,
) -> None:
    await cache.set_json("raw", {"label": "from-json"})
    loaded = await cache.get_as_model("raw", SampleModel)
    assert isinstance(loaded, SampleModel)
    assert loaded.label == "from-json"


@pytest.mark.asyncio
async def test_async_memory_delete_exists_counters(
    cache: MemoryCacheAsyncAdapter,
) -> None:
    assert await cache.exists("counter:n") is False
    assert await cache.incr("counter:n", 3) == 3
    assert await cache.incr("counter:n") == 4
    assert await cache.decr("counter:n", 2) == 2
    assert await cache.incrby("counter:n", 10) == 12
    assert await cache.exists("counter:n") is True
    assert await cache.delete("counter:n") == 1
    assert await cache.exists("counter:n") is False
    assert await cache.delete("counter:n") == 0


@pytest.mark.asyncio
async def test_async_memory_set_many_get_many(cache: MemoryCacheAsyncAdapter) -> None:
    await cache.set_many({})
    assert await cache.get_many([]) == {}

    await cache.set_many({"a": 1, "b": {"z": 2}}, ttl_seconds=None)
    out = await cache.get_many(["a", "b", "missing"])
    assert out["a"] == 1
    assert out["b"] == {"z": 2}
    assert out["missing"] is None


@pytest.mark.asyncio
async def test_async_memory_get_json_errors_delegate(
    cache: MemoryCacheAsyncAdapter,
) -> None:
    await cache.incr("c")
    with pytest.raises(SerializationError):
        await cache.get("c")

    await cache.set_model("mod", SampleModel(label="x"))
    with pytest.raises(SerializationError):
        await cache.get("mod")


@pytest.mark.asyncio
async def test_async_memory_concurrent_ops_are_serialized(
    cache: MemoryCacheAsyncAdapter,
) -> None:
    async def bump() -> None:
        for _ in range(50):
            await cache.incr("x")

    await asyncio.gather(bump(), bump())
    assert await cache.incr("x", 0) == 100


@pytest.mark.asyncio
async def test_async_memory_aclose_and_context_manager() -> None:
    async with MemoryCacheAsyncAdapter() as mem:
        await mem.set_json("x", 1)
    mem2 = MemoryCacheAsyncAdapter()
    await mem2.close()

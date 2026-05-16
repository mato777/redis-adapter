"""
End-to-end tests against Redis in Docker (`testcontainers[redis]`).

Requires a working Docker daemon. To skip locally: ``pytest -m "not e2e"``.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from cryptography.fernet import Fernet
from pydantic import BaseModel
from testcontainers.redis import RedisContainer

from async_redis_client import (
    DecryptionError,
    RedisCacheAsyncAdapter,
    RedisCacheSyncAdapter,
)

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session")
def redis_container_session():
    # Pin Redis server major version (client is stable redis-py from pyproject.toml).
    with RedisContainer("redis:8-alpine") as container:
        yield container


@pytest.fixture()
def fernet_key() -> bytes:
    return Fernet.generate_key()


@pytest.fixture()
def redis_sync_adapter(
    redis_container_session: RedisContainer,
    fernet_key: bytes,
) -> Iterator[RedisCacheSyncAdapter]:
    prefix = f"e2e:{uuid.uuid4().hex}:"
    client = redis_container_session.get_client(decode_responses=False)
    adapter = RedisCacheSyncAdapter(client, fernet_key=fernet_key, key_prefix=prefix)
    yield adapter
    client.close()


@pytest.fixture()
async def redis_async_adapter(
    redis_container_session: RedisContainer,
    fernet_key: bytes,
) -> AsyncIterator[RedisCacheAsyncAdapter]:
    prefix = f"e2e:{uuid.uuid4().hex}:"
    url = redis_url(redis_container_session)
    adapter = RedisCacheAsyncAdapter.from_standalone_url(
        url,
        fernet_key=fernet_key,
        key_prefix=prefix,
        decode_responses=False,
    )
    try:
        yield adapter
    finally:
        await adapter.close()


def redis_url(container: RedisContainer) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(container.port)
    return f"redis://{host}:{port}/0"


def test_e2e_sync_json_roundtrip(redis_sync_adapter: RedisCacheSyncAdapter) -> None:
    redis_sync_adapter.set_json("k", {"a": [1, 2, 3], "b": "x"})
    assert redis_sync_adapter.get_json("k") == {"a": [1, 2, 3], "b": "x"}


def test_e2e_sync_ttl_positive(redis_sync_adapter: RedisCacheSyncAdapter) -> None:
    redis_sync_adapter.set_json("exp", {"x": True}, ttl_seconds=60)
    ttl = redis_sync_adapter._client.ttl(redis_sync_adapter._full_key("exp"))
    assert isinstance(ttl, int)
    assert ttl > 0


def test_e2e_sync_counter_stored_plain(
    redis_sync_adapter: RedisCacheSyncAdapter,
) -> None:
    assert redis_sync_adapter.incr("counter:n", 3) == 3
    assert redis_sync_adapter.incr("counter:n", 2) == 5
    raw = redis_sync_adapter._client.get(redis_sync_adapter._full_key("counter:n"))
    assert raw == b"5"


def test_e2e_sync_model_roundtrip(redis_sync_adapter: RedisCacheSyncAdapter) -> None:
    class Item(BaseModel):
        sku: str
        qty: int

    redis_sync_adapter.set_model("i1", Item(sku="abc", qty=2))
    got = redis_sync_adapter.get_as_model("i1", Item)
    assert isinstance(got, Item)
    assert got.sku == "abc" and got.qty == 2


def test_e2e_sync_get_many_set_many(redis_sync_adapter: RedisCacheSyncAdapter) -> None:
    redis_sync_adapter.set_many({"a": 1, "b": {"z": 2}})
    out = redis_sync_adapter.get_many(["a", "b", "missing"])
    assert out["a"] == 1
    assert out["b"] == {"z": 2}
    assert out["missing"] is None


def test_e2e_sync_secondary_fernet_decrypts(
    redis_container_session: RedisContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary_old = Fernet.generate_key()
    primary_new = Fernet.generate_key()
    monkeypatch.delenv("CACHE_FERNET_KEY", raising=False)
    monkeypatch.delenv("CACHE_FERNET_KEY_SECONDARY", raising=False)

    prefix = f"e2e:{uuid.uuid4().hex}:"
    client = redis_container_session.get_client(decode_responses=False)
    try:
        legacy = RedisCacheSyncAdapter(
            client, fernet_key=primary_old, key_prefix=prefix
        )
        legacy.set_json("rotated", {"phase": "old"})

        reader = RedisCacheSyncAdapter(
            client,
            fernet_key=primary_new,
            fernet_key_secondary=primary_old,
            key_prefix=prefix,
        )
        assert reader.get_json("rotated") == {"phase": "old"}
    finally:
        client.close()


async def test_e2e_async_json_roundtrip(
    redis_async_adapter: RedisCacheAsyncAdapter,
) -> None:
    await redis_async_adapter.set_json("k", {"ok": True})
    assert await redis_async_adapter.get_json("k") == {"ok": True}


async def test_e2e_async_counter(redis_async_adapter: RedisCacheAsyncAdapter) -> None:
    assert await redis_async_adapter.incrby("c", 10) == 10
    assert await redis_async_adapter.decr("c", 3) == 7


async def test_e2e_async_model(redis_async_adapter: RedisCacheAsyncAdapter) -> None:
    class M(BaseModel):
        v: str

    await redis_async_adapter.set_model("m", M(v="hi"))
    got = await redis_async_adapter.get_as_model("m", M)
    assert got is not None and got.v == "hi"


async def test_e2e_async_set_many_get_many(
    redis_async_adapter: RedisCacheAsyncAdapter,
) -> None:
    await redis_async_adapter.set_many({"x": [1], "y": {"n": 2}})
    out = await redis_async_adapter.get_many(["x", "y", "gone"])
    assert out["x"] == [1]
    assert out["y"] == {"n": 2}
    assert out["gone"] is None


async def test_e2e_async_wrong_fernet_raises(
    redis_container_session: RedisContainer,
    fernet_key: bytes,
) -> None:
    url = redis_url(redis_container_session)
    prefix = f"e2e:{uuid.uuid4().hex}:"
    writer = RedisCacheAsyncAdapter.from_standalone_url(
        url,
        fernet_key=fernet_key,
        key_prefix=prefix,
        decode_responses=False,
    )
    await writer.set_json("k", 1)
    other = Fernet.generate_key()
    reader = RedisCacheAsyncAdapter.from_standalone_url(
        url,
        fernet_key=other,
        key_prefix=prefix,
        decode_responses=False,
    )
    try:
        with pytest.raises(DecryptionError):
            _ = await reader.get_json("k")
    finally:
        await writer.close()
        await reader.close()

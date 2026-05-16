from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from pydantic import BaseModel

from async_redis_client import (
    CacheClosedError,
    CacheKeyNotFoundError,
    DecryptionError,
    RedisCacheAsyncAdapter,
)


@pytest.fixture()
def fernet_key() -> bytes:
    return Fernet.generate_key()


@pytest.fixture()
async def async_redis(fernet_key: bytes):
    import fakeredis

    client = fakeredis.FakeAsyncRedis(decode_responses=False)
    adapter = RedisCacheAsyncAdapter(client, fernet_key=fernet_key)
    yield adapter


@pytest.mark.asyncio
async def test_async_json_roundtrip(async_redis: RedisCacheAsyncAdapter) -> None:
    await async_redis.set_json("k", {"ok": True})
    assert await async_redis.get_json("k") == {"ok": True}


@pytest.mark.asyncio
async def test_async_namespace_plus_key_prefix(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeAsyncRedis(decode_responses=False)
    cache = RedisCacheAsyncAdapter(
        r, fernet_key=fernet_key, namespace="ns:", key_prefix="p:"
    )
    await cache.set_json("x", 2)
    raw = await r.get(b"ns:p:x")
    assert raw is not None


@pytest.mark.asyncio
async def test_async_get_returns_none_for_miss(
    async_redis: RedisCacheAsyncAdapter,
) -> None:
    assert await async_redis.get("absent") is None


@pytest.mark.asyncio
async def test_async_json_ttl_sets_expire(async_redis: RedisCacheAsyncAdapter) -> None:
    await async_redis.set_json("exp", {"x": True}, ttl_seconds=60)
    assert await async_redis._client.ttl(async_redis._full_key("exp")) > 0  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_async_set_ttl_branch(async_redis: RedisCacheAsyncAdapter) -> None:
    await async_redis.set("t", [1], ttl_seconds=30)
    assert await async_redis._client.ttl(async_redis._full_key("t")) > 0  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_async_delete_exists_incr(async_redis: RedisCacheAsyncAdapter) -> None:
    assert await async_redis.exists("counter:n") is False
    assert await async_redis.incr("counter:n", 3) == 3
    assert await async_redis.incr("counter:n") == 4
    assert await async_redis.exists("counter:n") is True
    assert await async_redis.delete("counter:n") == 1
    assert await async_redis.exists("counter:n") is False


@pytest.mark.asyncio
async def test_async_set_many_get_many(async_redis: RedisCacheAsyncAdapter) -> None:
    await async_redis.set_many({})
    assert await async_redis.get_many([]) == {}

    await async_redis.set_many({"a": 1, "b": {"z": 2}}, ttl_seconds=None)
    out = await async_redis.get_many(["a", "b", "missing"])
    assert out["a"] == 1
    assert out["b"] == {"z": 2}
    assert out["missing"] is None


@pytest.mark.asyncio
async def test_async_set_many_ttl(async_redis: RedisCacheAsyncAdapter) -> None:
    await async_redis.set_many({"m": "v"}, ttl_seconds=120)
    ttl = await async_redis._client.ttl(async_redis._full_key("m"))  # type: ignore[attr-defined]
    assert ttl > 0


@pytest.mark.asyncio
async def test_async_model_ttl_and_miss(
    async_redis: RedisCacheAsyncAdapter,
) -> None:
    class Item(BaseModel):
        sku: str

    assert await async_redis.get_as_model("no-item", Item) is None

    await async_redis.set_model("i2", Item(sku="z"), ttl_seconds=45)
    got = await async_redis.get_as_model("i2", Item)
    assert got is not None and got.sku == "z"
    assert await async_redis._client.ttl(async_redis._full_key("i2")) > 0  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_from_standalone_url_builds_adapter(
    fernet_key: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fakeredis

    from async_redis_client.adapters.redis import async_adapter as aa_mod

    fake = fakeredis.FakeAsyncRedis(decode_responses=False)

    def fake_from_url(url: str, **kwargs: object) -> object:
        assert url == "redis://localhost/0"
        assert kwargs.get("encoding") == "utf-8"
        return fake

    monkeypatch.setattr(aa_mod.AsyncRedis, "from_url", fake_from_url)

    adapter = RedisCacheAsyncAdapter.from_standalone_url(
        "redis://localhost/0",
        fernet_key=fernet_key,
        key_prefix="pre:",
        encoding="utf-8",
    )
    await adapter.set_json("k", {"ok": True})
    assert await adapter.get_json("k") == {"ok": True}


@pytest.mark.asyncio
async def test_from_cluster_url_builds_adapter(
    fernet_key: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fakeredis

    from async_redis_client.adapters.redis import async_adapter as aa_mod

    fake = fakeredis.FakeAsyncRedis(decode_responses=False)

    def fake_from_url(url: str, **kwargs: object) -> object:
        assert url == "redis://localhost:7000"
        return fake

    monkeypatch.setattr(aa_mod.AsyncRedisCluster, "from_url", fake_from_url)

    adapter = RedisCacheAsyncAdapter.from_cluster_url(
        "redis://localhost:7000",
        fernet_key=fernet_key,
    )
    await adapter.set_json("c", 42)
    assert await adapter.get_json("c") == 42


@pytest.mark.asyncio
async def test_async_get_or_raise_if_missing_hit(
    async_redis: RedisCacheAsyncAdapter,
) -> None:
    await async_redis.set_json("k", {"x": 1})
    assert await async_redis.get_or_raise_if_missing("k") == {"x": 1}
    assert await async_redis.get_json_or_raise_if_missing("k") == {"x": 1}


@pytest.mark.asyncio
async def test_async_get_or_raise_if_missing_miss(
    async_redis: RedisCacheAsyncAdapter,
) -> None:
    with pytest.raises(CacheKeyNotFoundError) as excinfo:
        await async_redis.get_or_raise_if_missing("nope")
    assert excinfo.value.key == "nope"


@pytest.mark.asyncio
async def test_async_get_or_raise_if_missing_json_null_stored(
    async_redis: RedisCacheAsyncAdapter,
) -> None:
    await async_redis.set_json("nullkey", None)
    assert await async_redis.get_or_raise_if_missing("nullkey") is None


@pytest.mark.asyncio
async def test_async_counter(async_redis: RedisCacheAsyncAdapter) -> None:
    assert await async_redis.incrby("c", 10) == 10
    assert await async_redis.decr("c", 3) == 7


@pytest.mark.asyncio
async def test_async_model(async_redis: RedisCacheAsyncAdapter) -> None:
    class M(BaseModel):
        v: str

    await async_redis.set_model("m", M(v="hi"))
    got = await async_redis.get_as_model("m", M)
    assert got is not None and got.v == "hi"


@pytest.mark.asyncio
async def test_async_secondary_decrypts_legacy() -> None:
    import fakeredis

    primary_old = Fernet.generate_key()
    primary_new = Fernet.generate_key()
    r = fakeredis.FakeAsyncRedis(decode_responses=False)
    legacy = RedisCacheAsyncAdapter(r, fernet_key=primary_old)
    await legacy.set_json("a", [1, 2])

    reader = RedisCacheAsyncAdapter(
        r,
        fernet_key=primary_new,
        fernet_key_secondary=primary_old,
    )
    assert await reader.get_json("a") == [1, 2]


@pytest.mark.asyncio
async def test_async_both_keys_fail_raises() -> None:
    import fakeredis

    r = fakeredis.FakeAsyncRedis(decode_responses=False)
    write = RedisCacheAsyncAdapter(r, fernet_key=Fernet.generate_key())
    await write.set_json("x", 1)
    reader = RedisCacheAsyncAdapter(
        r,
        fernet_key=Fernet.generate_key(),
        fernet_key_secondary=Fernet.generate_key(),
    )
    with pytest.raises(DecryptionError):
        await reader.get_json("x")


@pytest.mark.asyncio
async def test_async_close_owns_client_calls_redis_aclose(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeAsyncRedis(decode_responses=False)
    closed: list[int] = []
    orig_aclose = r.aclose

    async def track_aclose(close_connection_pool: bool | None = None) -> None:
        closed.append(1)
        await orig_aclose(close_connection_pool)

    r.aclose: object = track_aclose

    adapter = RedisCacheAsyncAdapter(r, fernet_key=fernet_key, owns_client=True)
    await adapter.close()
    assert closed == [1]
    await adapter.aclose()
    assert closed == [1]


@pytest.mark.asyncio
async def test_async_close_injected_client_is_noop(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeAsyncRedis(decode_responses=False)
    closed: list[int] = []
    orig_aclose = r.aclose

    async def track_aclose(close_connection_pool: bool | None = None) -> None:
        closed.append(1)
        await orig_aclose(close_connection_pool)

    r.aclose: object = track_aclose

    adapter = RedisCacheAsyncAdapter(r, fernet_key=fernet_key, owns_client=False)
    await adapter.close()
    assert closed == []


@pytest.mark.asyncio
async def test_async_context_manager_exits_close(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeAsyncRedis(decode_responses=False)
    closed: list[int] = []
    orig_aclose = r.aclose

    async def track_aclose(close_connection_pool: bool | None = None) -> None:
        closed.append(1)
        await orig_aclose(close_connection_pool)

    r.aclose: object = track_aclose

    async with RedisCacheAsyncAdapter(r, fernet_key=fernet_key, owns_client=True):
        pass
    assert closed == [1]


@pytest.mark.asyncio
async def test_async_operations_raise_after_close_owned(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeAsyncRedis(decode_responses=False)
    adapter = RedisCacheAsyncAdapter(r, fernet_key=fernet_key, owns_client=True)
    await adapter.set_json("k", 1)
    await adapter.close()
    with pytest.raises(CacheClosedError):
        await adapter.get_json("k")


@pytest.mark.asyncio
async def test_async_injected_still_usable_after_adapter_close(
    fernet_key: bytes,
) -> None:
    import fakeredis

    r = fakeredis.FakeAsyncRedis(decode_responses=False)
    adapter = RedisCacheAsyncAdapter(r, fernet_key=fernet_key, owns_client=False)
    await adapter.set_json("k", 1)
    await adapter.close()
    assert await adapter.get_json("k") == 1


@pytest.mark.asyncio
async def test_async_reenter_context_after_close_raises(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeAsyncRedis(decode_responses=False)
    adapter = RedisCacheAsyncAdapter(r, fernet_key=fernet_key, owns_client=True)
    await adapter.close()
    with pytest.raises(CacheClosedError):
        await adapter.__aenter__()

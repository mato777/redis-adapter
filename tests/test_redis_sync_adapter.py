from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from pydantic import BaseModel

from async_redis_client import (
    CacheClosedError,
    CacheKeyNotFoundError,
    DecryptionError,
    RedisCacheSyncAdapter,
)
from async_redis_client.adapters.memory import MemoryCacheSyncAdapter


@pytest.fixture()
def fernet_key() -> bytes:
    return Fernet.generate_key()


@pytest.fixture()
def sync_redis(fernet_key: bytes):
    import fakeredis

    client = fakeredis.FakeRedis(decode_responses=False)
    adapter = RedisCacheSyncAdapter(client, fernet_key=fernet_key)
    yield adapter


def test_sync_json_roundtrip(sync_redis: RedisCacheSyncAdapter) -> None:
    sync_redis.set_json("k", {"a": [1, 2, 3], "b": "x"})
    assert sync_redis.get_json("k") == {"a": [1, 2, 3], "b": "x"}


def test_sync_get_or_raise_if_missing_hit(sync_redis: RedisCacheSyncAdapter) -> None:
    sync_redis.set_json("k", {"x": 1})
    assert sync_redis.get_or_raise_if_missing("k") == {"x": 1}
    assert sync_redis.get_json_or_raise_if_missing("k") == {"x": 1}


def test_sync_get_or_raise_if_missing_miss(sync_redis: RedisCacheSyncAdapter) -> None:
    with pytest.raises(CacheKeyNotFoundError) as excinfo:
        sync_redis.get_or_raise_if_missing("nope")
    assert excinfo.value.key == "nope"


def test_sync_get_or_raise_if_missing_json_null_stored(
    sync_redis: RedisCacheSyncAdapter,
) -> None:
    sync_redis.set_json("nullkey", None)
    assert sync_redis.get_or_raise_if_missing("nullkey") is None


def test_sync_key_prefix(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeRedis(decode_responses=False)
    cache = RedisCacheSyncAdapter(r, fernet_key=fernet_key, key_prefix="p:")
    cache.set_json("k", 1)
    raw = r.get(b"p:k")
    assert raw is not None


def test_sync_namespace_only(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeRedis(decode_responses=False)
    cache = RedisCacheSyncAdapter(r, fernet_key=fernet_key, namespace="myapp:")
    cache.set_json("k", 1)
    raw = r.get(b"myapp:k")
    assert raw is not None
    assert cache.get_json("k") == 1


def test_sync_namespace_plus_key_prefix(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeRedis(decode_responses=False)
    cache = RedisCacheSyncAdapter(
        r, fernet_key=fernet_key, namespace="myapp:", key_prefix="cache:"
    )
    cache.set_json("k", 1)
    raw = r.get(b"myapp:cache:k")
    assert raw is not None


def test_sync_ttl_sets_expire(sync_redis: RedisCacheSyncAdapter) -> None:
    sync_redis.set_json("exp", {"x": True}, ttl_seconds=60)
    # fakeredis returns TTL in seconds
    assert sync_redis._client.ttl(sync_redis._full_key("exp")) > 0  # type: ignore[attr-defined]


def test_sync_counter_plaintext(sync_redis: RedisCacheSyncAdapter) -> None:
    assert sync_redis.incr("counter:n", 3) == 3
    assert sync_redis.incr("counter:n", 2) == 5
    assert sync_redis.decr("counter:n", 4) == 1
    raw = sync_redis._client.get(sync_redis._full_key("counter:n"))
    assert raw == b"1"


def test_sync_model_roundtrip(sync_redis: RedisCacheSyncAdapter) -> None:
    class Item(BaseModel):
        sku: str
        qty: int

    sync_redis.set_model("i1", Item(sku="abc", qty=2))
    got = sync_redis.get_as_model("i1", Item)
    assert isinstance(got, Item)
    assert got.sku == "abc" and got.qty == 2


def test_sync_wrong_fernet_raises(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeRedis(decode_responses=False)
    c1 = RedisCacheSyncAdapter(r, fernet_key=fernet_key)
    c1.set_json("k", 1)
    other = Fernet.generate_key()
    c2 = RedisCacheSyncAdapter(r, fernet_key=other)
    with pytest.raises(DecryptionError):
        c2.get_json("k")


def test_sync_secondary_fernet_decrypts_legacy_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fakeredis

    primary_old = Fernet.generate_key()
    primary_new = Fernet.generate_key()
    monkeypatch.delenv("CACHE_FERNET_KEY", raising=False)
    monkeypatch.delenv("CACHE_FERNET_KEY_SECONDARY", raising=False)

    r = fakeredis.FakeRedis(decode_responses=False)
    legacy = RedisCacheSyncAdapter(r, fernet_key=primary_old)
    legacy.set_json("rotated", {"phase": "old"})

    reader = RedisCacheSyncAdapter(
        r,
        fernet_key=primary_new,
        fernet_key_secondary=primary_old,
    )
    assert reader.get_json("rotated") == {"phase": "old"}


def test_sync_secondary_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import fakeredis

    primary_old = Fernet.generate_key()
    primary_new = Fernet.generate_key()
    monkeypatch.delenv("CACHE_FERNET_KEY", raising=False)
    monkeypatch.setenv("CACHE_FERNET_KEY_SECONDARY", primary_old.decode("ascii"))

    r = fakeredis.FakeRedis(decode_responses=False)
    legacy = RedisCacheSyncAdapter(r, fernet_key=primary_old)
    legacy.set_json("k", "env-fallback")

    reader = RedisCacheSyncAdapter(r, fernet_key=primary_new)
    assert reader.get_json("k") == "env-fallback"


def test_sync_invalid_json_blob_raises(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeRedis(decode_responses=False)
    cache = RedisCacheSyncAdapter(r, fernet_key=fernet_key)
    cache._client.set(cache._full_key("bad"), b"not-fernet")  # type: ignore[attr-defined]
    with pytest.raises(DecryptionError):
        cache.get_json("bad")


def test_sync_get_many_set_many(sync_redis: RedisCacheSyncAdapter) -> None:
    sync_redis.set_many({"a": 1, "b": {"z": 2}}, ttl_seconds=None)
    out = sync_redis.get_many(["a", "b", "missing"])
    assert out["a"] == 1
    assert out["b"] == {"z": 2}
    assert out["missing"] is None


def test_sync_empty_set_many_and_get_many(sync_redis: RedisCacheSyncAdapter) -> None:
    sync_redis.set_many({})
    assert sync_redis.get_many([]) == {}


def test_sync_exists_and_incrby(sync_redis: RedisCacheSyncAdapter) -> None:
    assert sync_redis.exists("nope") is False
    sync_redis.set_json("nope", 1)
    assert sync_redis.exists("nope") is True
    assert sync_redis.incrby("counter:x", 5) == 5


def test_sync_get_as_model_missing(sync_redis: RedisCacheSyncAdapter) -> None:
    class Item(BaseModel):
        sku: str

    assert sync_redis.get_as_model("missing-model", Item) is None


def test_sync_set_model_without_ttl(sync_redis: RedisCacheSyncAdapter) -> None:
    class Item(BaseModel):
        sku: str

    sync_redis.set_model("plain", Item(sku="z"))
    got = sync_redis.get_as_model("plain", Item)
    assert got is not None
    assert got.sku == "z"


def test_sync_set_model_with_ttl(sync_redis: RedisCacheSyncAdapter) -> None:
    class Item(BaseModel):
        sku: str

    sync_redis.set_model("ttl-item", Item(sku="t"), ttl_seconds=30)
    got = sync_redis.get_as_model("ttl-item", Item)
    assert got is not None
    assert got.sku == "t"
    assert sync_redis._client.ttl(sync_redis._full_key("ttl-item")) > 0  # type: ignore[attr-defined]


def test_sync_delete(sync_redis: RedisCacheSyncAdapter) -> None:
    sync_redis.set_json("del-me", 1)
    assert sync_redis.delete("del-me") == 1
    assert sync_redis.get_json("del-me") is None


def test_sync_from_standalone_url(
    fernet_key: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fakeredis

    from async_redis_client.adapters.redis import sync_adapter as mod

    fake = fakeredis.FakeRedis(decode_responses=False)
    monkeypatch.setattr(mod.Redis, "from_url", lambda url, **kw: fake)
    adapter = RedisCacheSyncAdapter.from_standalone_url(
        "redis://localhost/1",
        fernet_key=fernet_key,
        namespace="ns:",
    )
    adapter.set_json("k", 1)
    assert adapter.get_json("k") == 1


def test_sync_from_cluster_url(
    fernet_key: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fakeredis

    from async_redis_client.adapters.redis import sync_adapter as mod

    fake = fakeredis.FakeRedis(decode_responses=False)
    monkeypatch.setattr(mod.RedisCluster, "from_url", lambda url, **kw: fake)
    adapter = RedisCacheSyncAdapter.from_cluster_url(
        "redis://localhost:7000",
        fernet_key=fernet_key,
    )
    adapter.set_json("c", 2)
    assert adapter.get_json("c") == 2


def test_memory_adapter_json_and_counter() -> None:
    mem = MemoryCacheSyncAdapter()
    mem.set_json("x", [1, 2])
    assert mem.get_json("x") == [1, 2]
    assert mem.incr("n") == 1
    assert mem.incr("n") == 2


def test_memory_get_or_raise_if_missing() -> None:
    mem = MemoryCacheSyncAdapter()
    mem.set_json("x", 1)
    assert mem.get_or_raise_if_missing("x") == 1
    with pytest.raises(CacheKeyNotFoundError):
        mem.get_or_raise_if_missing("missing")


def test_sync_close_owns_client_calls_redis_close(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeRedis(decode_responses=False)
    closed: list[int] = []
    orig_close = r.close

    def track_close() -> None:
        closed.append(1)
        orig_close()

    r.close: object = track_close

    adapter = RedisCacheSyncAdapter(r, fernet_key=fernet_key, owns_client=True)
    adapter.close()
    assert closed == [1]
    adapter.close()
    assert closed == [1]


def test_sync_close_injected_client_is_noop(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeRedis(decode_responses=False)
    closed: list[int] = []
    orig_close = r.close

    def track_close() -> None:
        closed.append(1)
        orig_close()

    r.close: object = track_close

    adapter = RedisCacheSyncAdapter(r, fernet_key=fernet_key, owns_client=False)
    adapter.close()
    assert closed == []


def test_sync_context_manager_exits_close(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeRedis(decode_responses=False)
    closed: list[int] = []
    orig_close = r.close

    def track_close() -> None:
        closed.append(1)
        orig_close()

    r.close: object = track_close

    with RedisCacheSyncAdapter(r, fernet_key=fernet_key, owns_client=True):
        pass
    assert closed == [1]


def test_sync_operations_raise_after_close_owned(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeRedis(decode_responses=False)
    adapter = RedisCacheSyncAdapter(r, fernet_key=fernet_key, owns_client=True)
    adapter.set_json("k", 1)
    adapter.close()
    with pytest.raises(CacheClosedError):
        adapter.get_json("k")


def test_sync_injected_still_usable_after_adapter_close(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeRedis(decode_responses=False)
    adapter = RedisCacheSyncAdapter(r, fernet_key=fernet_key, owns_client=False)
    adapter.set_json("k", 1)
    adapter.close()
    assert adapter.get_json("k") == 1


def test_sync_reenter_context_after_close_raises(fernet_key: bytes) -> None:
    import fakeredis

    r = fakeredis.FakeRedis(decode_responses=False)
    adapter = RedisCacheSyncAdapter(r, fernet_key=fernet_key, owns_client=True)
    adapter.close()
    with pytest.raises(CacheClosedError):
        adapter.__enter__()


def test_memory_adapter_close_and_context_manager() -> None:
    with MemoryCacheSyncAdapter() as mem:
        mem.set_json("x", 1)
    mem2 = MemoryCacheSyncAdapter()
    mem2.close()

from __future__ import annotations

import pytest

from async_redis_client import PubSubClosedError, RedisPubSubAsyncAdapter


@pytest.fixture()
async def async_pubsub() -> RedisPubSubAsyncAdapter:
    import fakeredis

    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    return RedisPubSubAsyncAdapter(client)


@pytest.mark.asyncio
async def test_async_publish_and_receive(
    async_pubsub: RedisPubSubAsyncAdapter,
) -> None:
    sub = await async_pubsub.subscribe("events")
    try:
        receivers = await async_pubsub.publish("events", "hello")
        assert receivers >= 1
        msg = await sub.get_message(timeout=2.0)
        assert msg is not None
        assert msg.channel == "events"
        assert msg.data == "hello"
    finally:
        await sub.close()


@pytest.mark.asyncio
async def test_async_psubscribe_pattern(async_pubsub: RedisPubSubAsyncAdapter) -> None:
    sub = await async_pubsub.psubscribe("event*")
    try:
        await async_pubsub.publish("events", "match")
        msg = await sub.get_message(timeout=2.0)
        assert msg is not None
        assert msg.channel == "events"
        assert msg.data == "match"
        assert msg.pattern == "event*"
    finally:
        await sub.close()


@pytest.mark.asyncio
async def test_async_listen(async_pubsub: RedisPubSubAsyncAdapter) -> None:
    sub = await async_pubsub.subscribe("stream")
    try:
        await async_pubsub.publish("stream", "a")
        await async_pubsub.publish("stream", "b")
        got: list[str | bytes] = []
        async for msg in sub.listen():
            got.append(msg.data)
            if len(got) >= 2:
                break
        assert got == ["a", "b"]
    finally:
        await sub.close()


@pytest.mark.asyncio
async def test_async_closed_adapter_raises(
    async_pubsub: RedisPubSubAsyncAdapter,
) -> None:
    await async_pubsub.close()
    with pytest.raises(PubSubClosedError):
        await async_pubsub.publish("x", "y")


@pytest.mark.asyncio
async def test_close_adapter_before_subscription(
    async_pubsub: RedisPubSubAsyncAdapter,
) -> None:
    sub = await async_pubsub.subscribe("orphan")
    await async_pubsub.close()
    with pytest.raises(PubSubClosedError):
        await async_pubsub.publish("orphan", "late")
    await sub.close()


@pytest.mark.asyncio
async def test_async_subscription_unsubscribe_and_close(
    async_pubsub: RedisPubSubAsyncAdapter,
) -> None:
    sub = await async_pubsub.subscribe("a", "b")
    try:
        await sub.unsubscribe("a")
        await sub.unsubscribe()
        await sub.close()
        await sub.close()
        with pytest.raises(PubSubClosedError):
            await sub.get_message()
    finally:
        if not sub._closed:
            await sub.close()


@pytest.mark.asyncio
async def test_async_get_message_timeout_returns_none(
    async_pubsub: RedisPubSubAsyncAdapter,
) -> None:
    sub = await async_pubsub.subscribe("quiet")
    try:
        assert await sub.get_message(timeout=0.01) is None
    finally:
        await sub.close()


@pytest.mark.asyncio
async def test_async_punsubscribe_with_and_without_patterns(
    async_pubsub: RedisPubSubAsyncAdapter,
) -> None:
    sub = await async_pubsub.psubscribe("evt*")
    try:
        await sub.punsubscribe("evt*")
    finally:
        await sub.close()

    sub_all = await async_pubsub.psubscribe("other*")
    try:
        await sub_all.punsubscribe()
    finally:
        await sub_all.close()


@pytest.mark.asyncio
async def test_async_closed_subscription_raises(
    async_pubsub: RedisPubSubAsyncAdapter,
) -> None:
    sub = await async_pubsub.subscribe("x")
    await sub.close()
    with pytest.raises(PubSubClosedError):
        await sub.unsubscribe("x")


@pytest.mark.asyncio
async def test_async_from_standalone_url_and_owns_client_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fakeredis

    from async_redis_client.adapters.redis import pubsub_async_adapter as mod

    fake = fakeredis.FakeAsyncRedis(decode_responses=True)
    closed: list[int] = []
    orig_aclose = fake.aclose

    async def track_aclose() -> None:
        closed.append(1)
        await orig_aclose()

    fake.aclose: object = track_aclose

    def fake_from_url(url: str, **kwargs: object) -> object:
        assert url == "redis://localhost/9"
        return fake

    monkeypatch.setattr(mod.AsyncRedis, "from_url", fake_from_url)
    adapter = RedisPubSubAsyncAdapter.from_standalone_url("redis://localhost/9")
    async with adapter as entered:
        assert entered is adapter
    assert closed == [1]
    await adapter.aclose()
    assert closed == [1]


@pytest.mark.asyncio
async def test_async_from_cluster_url(monkeypatch: pytest.MonkeyPatch) -> None:
    import fakeredis

    from async_redis_client.adapters.redis import pubsub_async_adapter as mod

    fake = fakeredis.FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr(mod.AsyncRedisCluster, "from_url", lambda url, **kw: fake)
    adapter = RedisPubSubAsyncAdapter.from_cluster_url("redis://cluster/0")
    sub = await adapter.subscribe("c")
    try:
        await adapter.publish("c", "v")
        msg = await sub.get_message(timeout=2.0)
        assert msg is not None
        assert msg.data == "v"
    finally:
        await sub.close()
        await adapter.close()

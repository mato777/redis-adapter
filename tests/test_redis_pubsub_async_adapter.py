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

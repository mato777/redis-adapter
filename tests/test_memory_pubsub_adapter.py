from __future__ import annotations

import pytest

from async_redis_client import (
    MemoryPubSubAsyncAdapter,
    MemoryPubSubSyncAdapter,
    PubSubClosedError,
)


def test_memory_sync_pubsub() -> None:
    bus = MemoryPubSubSyncAdapter()
    sub = bus.subscribe("room")
    try:
        assert bus.publish("room", "hi") == 1
        msg = sub.get_message(timeout=1.0)
        assert msg is not None
        assert msg.data == "hi"
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_memory_async_pubsub() -> None:
    bus = MemoryPubSubAsyncAdapter()
    sub = await bus.subscribe("room")
    try:
        assert await bus.publish("room", "async") == 1
        msg = await sub.get_message(timeout=1.0)
        assert msg is not None
        assert msg.data == "async"
    finally:
        await sub.close()


def test_memory_sync_pattern() -> None:
    bus = MemoryPubSubSyncAdapter()
    sub = bus.psubscribe("event*")
    try:
        bus.publish("events", "p")
        msg = sub.get_message(timeout=1.0)
        assert msg is not None
        assert msg.pattern == "event*"
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_memory_async_pattern() -> None:
    bus = MemoryPubSubAsyncAdapter()
    sub = await bus.psubscribe("event*")
    try:
        assert await bus.publish("events", "async-p") == 1
        msg = await sub.get_message(timeout=1.0)
        assert msg is not None
        assert msg.pattern == "event*"
        assert msg.data == "async-p"
    finally:
        await sub.close()


def test_memory_sync_rejects_multiple_channels() -> None:
    bus = MemoryPubSubSyncAdapter()
    with pytest.raises(ValueError, match="one channel"):
        bus.subscribe("a", "b")


def test_memory_sync_rejects_multiple_patterns() -> None:
    bus = MemoryPubSubSyncAdapter()
    with pytest.raises(ValueError, match="one pattern"):
        bus.psubscribe("a*", "b*")


@pytest.mark.asyncio
async def test_memory_async_rejects_multiple_channels() -> None:
    bus = MemoryPubSubAsyncAdapter()
    with pytest.raises(ValueError, match="one channel"):
        await bus.subscribe("a", "b")


@pytest.mark.asyncio
async def test_memory_async_rejects_multiple_patterns() -> None:
    bus = MemoryPubSubAsyncAdapter()
    with pytest.raises(ValueError, match="one pattern"):
        await bus.psubscribe("a*", "b*")


def test_memory_sync_context_manager_and_closed_adapter() -> None:
    with MemoryPubSubSyncAdapter() as bus:
        assert bus.publish("c", "ok") == 0
    bus2 = MemoryPubSubSyncAdapter()
    bus2.close()
    with pytest.raises(PubSubClosedError):
        bus2.publish("c", "late")


@pytest.mark.asyncio
async def test_memory_async_context_manager_and_closed_adapter() -> None:
    async with MemoryPubSubAsyncAdapter() as bus:
        assert await bus.publish("c", "ok") == 0
    bus2 = MemoryPubSubAsyncAdapter()
    await bus2.close()
    with pytest.raises(PubSubClosedError):
        await bus2.publish("c", "late")


def test_memory_sync_subscription_lifecycle() -> None:
    bus = MemoryPubSubSyncAdapter()
    sub = bus.subscribe("room")
    try:
        bus.publish("room", "one")
        assert sub.get_message(timeout=None) is not None
        assert sub.get_message(timeout=0.01) is None
        bus.publish("room", "two")
        received = []
        for msg in sub.listen():
            received.append(msg.data)
            if len(received) >= 1:
                break
        assert received == ["two"]
        sub.unsubscribe()
        with pytest.raises(PubSubClosedError):
            sub.get_message()
        sub.close()
        sub.close()
    finally:
        if not sub._closed:
            sub.close()


def test_memory_sync_pattern_unsubscribe_closes() -> None:
    bus = MemoryPubSubSyncAdapter()
    sub = bus.psubscribe("evt*")
    sub.punsubscribe()
    with pytest.raises(PubSubClosedError):
        sub.get_message()


@pytest.mark.asyncio
async def test_memory_async_subscription_lifecycle() -> None:
    bus = MemoryPubSubAsyncAdapter()
    sub = await bus.subscribe("room")
    try:
        await bus.publish("room", "one")
        assert await sub.get_message(timeout=None) is not None
        assert await sub.get_message(timeout=0.01) is None
        await bus.publish("room", "two")
        received: list[str | bytes] = []
        async for msg in sub.listen():
            received.append(msg.data)
            if len(received) >= 1:
                break
        assert received == ["two"]
        await sub.unsubscribe()
        with pytest.raises(PubSubClosedError):
            await sub.get_message()
        await sub.close()
        await sub.close()
    finally:
        if not sub._closed:
            await sub.close()


@pytest.mark.asyncio
async def test_memory_async_pattern_unsubscribe_closes() -> None:
    bus = MemoryPubSubAsyncAdapter()
    sub = await bus.psubscribe("evt*")
    await sub.punsubscribe()
    with pytest.raises(PubSubClosedError):
        await sub.get_message()


@pytest.mark.asyncio
async def test_memory_async_listen_stops_on_none_sentinel() -> None:
    bus = MemoryPubSubAsyncAdapter()
    sub = await bus.subscribe("ch")
    sub._queue.put_nowait(None)
    collected = [msg async for msg in sub.listen()]
    assert collected == []


def test_memory_sync_listen_stops_on_none_sentinel() -> None:
    bus = MemoryPubSubSyncAdapter()
    sub = bus.subscribe("ch")
    sub._queue.put(None)
    collected = list(sub.listen())
    assert collected == []

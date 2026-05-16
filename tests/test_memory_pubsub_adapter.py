from __future__ import annotations

import pytest

from async_redis_client import (
    MemoryPubSubAsyncAdapter,
    MemoryPubSubSyncAdapter,
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

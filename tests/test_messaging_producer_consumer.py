from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from pydantic import BaseModel

from async_redis_client import (
    MemoryPubSubAsyncAdapter,
    MemoryPubSubSyncAdapter,
    PubSubConsumerAsync,
    PubSubConsumerSync,
    PubSubProducerAsync,
    PubSubProducerSync,
)


class OrderCreated(BaseModel):
    order_id: int
    sku: str


@dataclass(frozen=True, slots=True)
class Ping:
    text: str


@pytest.mark.asyncio
async def test_async_producer_consumer_with_dependencies() -> None:
    bus = MemoryPubSubAsyncAdapter()
    received: list[OrderCreated] = []
    db_calls: list[str] = []

    class FakeDb:
        def record(self, sku: str) -> None:
            db_calls.append(sku)

    db = FakeDb()

    async def on_order(event: OrderCreated, db: FakeDb) -> None:
        db.record(event.sku)
        received.append(event)

    producer = PubSubProducerAsync(bus, "orders", OrderCreated)
    consumer = PubSubConsumerAsync(bus, "orders", OrderCreated, on_order, db=db)

    task = asyncio.create_task(consumer.run(max_messages=1))
    await asyncio.sleep(0.05)
    await producer.publish(OrderCreated(order_id=42, sku="ABC"))
    await task

    assert received == [OrderCreated(order_id=42, sku="ABC")]
    assert db_calls == ["ABC"]


@pytest.mark.asyncio
async def test_async_consumer_stop_event() -> None:
    bus = MemoryPubSubAsyncAdapter()
    stop = asyncio.Event()
    count = 0

    async def on_ping(msg: Ping) -> None:
        nonlocal count
        count += 1
        stop.set()

    consumer = PubSubConsumerAsync(bus, "ping", Ping, on_ping)
    producer = PubSubProducerAsync(bus, "ping", Ping)

    task = asyncio.create_task(consumer.run(stop_event=stop))
    await asyncio.sleep(0.05)
    await producer.publish(Ping(text="hi"))
    await asyncio.wait_for(task, timeout=2.0)
    assert count == 1


def test_sync_producer_consumer() -> None:
    bus = MemoryPubSubSyncAdapter()
    seen: list[Ping] = []

    def on_ping(msg: Ping, *, tag: str) -> None:
        seen.append(msg)
        assert tag == "test"

    producer = PubSubProducerSync(bus, "pings", Ping)
    consumer = PubSubConsumerSync(bus, "pings", Ping, on_ping, tag="test")

    import threading
    import time

    thread = threading.Thread(target=consumer.run, kwargs={"max_messages": 1})
    thread.start()
    time.sleep(0.05)
    producer.publish(Ping(text="sync"))
    thread.join(timeout=2.0)
    assert not thread.is_alive()
    assert seen == [Ping(text="sync")]


def test_consumer_missing_dependency_raises() -> None:
    bus = MemoryPubSubSyncAdapter()

    def needs_db(_: Ping, db: object) -> None:
        pass

    with pytest.raises(TypeError, match="missing required parameters"):
        PubSubConsumerSync(bus, "x", Ping, needs_db)

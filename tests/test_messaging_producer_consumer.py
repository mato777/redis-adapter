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
    PubSubSerializationError,
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
async def test_async_consumer_stop_event_max_messages() -> None:
    bus = MemoryPubSubAsyncAdapter()
    seen: list[int] = []

    async def on_ping(msg: Ping) -> None:
        seen.append(1)

    consumer = PubSubConsumerAsync(bus, "ping", Ping, on_ping)
    producer = PubSubProducerAsync(bus, "ping", Ping)

    task = asyncio.create_task(consumer.run(max_messages=2))
    await asyncio.sleep(0.05)
    await producer.publish(Ping(text="a"))
    await producer.publish(Ping(text="b"))
    await producer.publish(Ping(text="c"))
    await asyncio.wait_for(task, timeout=2.0)
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_async_consumer_stop_event_polls_until_set() -> None:
    bus = MemoryPubSubAsyncAdapter()
    stop = asyncio.Event()

    async def on_ping(_: Ping) -> None:
        pass

    consumer = PubSubConsumerAsync(bus, "idle", Ping, on_ping)
    task = asyncio.create_task(consumer.run(stop_event=stop))
    await asyncio.sleep(0.6)
    stop.set()
    await asyncio.wait_for(task, timeout=2.0)


@pytest.mark.asyncio
async def test_async_consumer_stop_event_with_max_messages() -> None:
    bus = MemoryPubSubAsyncAdapter()
    stop = asyncio.Event()
    seen: list[str] = []

    async def on_ping(msg: Ping) -> None:
        seen.append(msg.text)

    consumer = PubSubConsumerAsync(bus, "ping", Ping, on_ping)
    producer = PubSubProducerAsync(bus, "ping", Ping)

    task = asyncio.create_task(
        consumer.run(stop_event=stop, max_messages=2),
    )
    await asyncio.sleep(0.05)
    await producer.publish(Ping(text="a"))
    await producer.publish(Ping(text="b"))
    await asyncio.wait_for(task, timeout=2.0)
    assert seen == ["a", "b"]


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


def test_consumer_rejects_bound_method() -> None:
    bus = MemoryPubSubSyncAdapter()

    class Svc:
        def on_ping(self, msg: Ping) -> None:
            pass

    with pytest.raises(TypeError, match="plain function"):
        PubSubConsumerSync(bus, "x", Ping, Svc().on_ping)


@pytest.mark.asyncio
async def test_async_consumer_invalid_json_raises() -> None:
    bus = MemoryPubSubAsyncAdapter()
    seen: list[Ping] = []

    async def on_ping(msg: Ping) -> None:
        seen.append(msg)

    consumer = PubSubConsumerAsync(bus, "bad", Ping, on_ping)
    task = asyncio.create_task(consumer.run(max_messages=1))
    await asyncio.sleep(0.05)
    await bus.publish("bad", b"not-json")
    with pytest.raises(PubSubSerializationError):
        await asyncio.wait_for(task, timeout=2.0)
    assert seen == []


def test_sync_consumer_rejects_async_handler() -> None:
    bus = MemoryPubSubSyncAdapter()

    async def async_handler(_: Ping) -> None:
        pass

    consumer = PubSubConsumerSync(bus, "x", Ping, async_handler)
    producer = PubSubProducerSync(bus, "x", Ping)

    import threading
    import time

    errors: list[BaseException] = []

    def run_consumer() -> None:
        try:
            consumer.run(max_messages=1)
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run_consumer)
    thread.start()
    time.sleep(0.05)
    producer.publish(Ping(text="x"))
    thread.join(timeout=2.0)
    assert len(errors) == 1
    assert isinstance(errors[0], TypeError)
    assert "async handlers" in str(errors[0])

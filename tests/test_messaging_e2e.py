"""
End-to-end tests for typed pub/sub producer and consumer against Redis in Docker.

Requires a working Docker daemon. To skip locally: ``pytest -m "not e2e"``.
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from pydantic import BaseModel
from testcontainers.redis import RedisContainer

from async_redis_client import (
    PubSubConsumerAsync,
    PubSubConsumerSync,
    PubSubProducerAsync,
    PubSubProducerSync,
    RedisPubSubAsyncAdapter,
    RedisPubSubSyncAdapter,
)

pytestmark = pytest.mark.e2e


class OrderCreated(BaseModel):
    order_id: int
    sku: str


@pytest.fixture(scope="session")
def redis_container_session():
    with RedisContainer("redis:8-alpine") as container:
        yield container


def redis_url(container: RedisContainer) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(container.port)
    return f"redis://{host}:{port}/0"


@pytest.fixture()
def sync_pubsub_e2e(
    redis_container_session: RedisContainer,
) -> Iterator[RedisPubSubSyncAdapter]:
    prefix = f"e2e-msg:{uuid.uuid4().hex}:"
    client = redis_container_session.get_client(decode_responses=True)
    adapter = RedisPubSubSyncAdapter(client, channel_prefix=prefix)
    yield adapter
    adapter.close()


@pytest.fixture()
async def async_pubsub_e2e(
    redis_container_session: RedisContainer,
) -> AsyncIterator[RedisPubSubAsyncAdapter]:
    prefix = f"e2e-msg:{uuid.uuid4().hex}:"
    adapter = RedisPubSubAsyncAdapter.from_standalone_url(
        redis_url(redis_container_session),
        channel_prefix=prefix,
        decode_responses=True,
    )
    try:
        yield adapter
    finally:
        await adapter.close()


def test_e2e_sync_producer_consumer(
    sync_pubsub_e2e: RedisPubSubSyncAdapter,
) -> None:
    received: list[OrderCreated] = []
    channel = f"orders-{uuid.uuid4().hex}"

    def on_order(event: OrderCreated) -> None:
        received.append(event)

    producer = PubSubProducerSync(sync_pubsub_e2e, channel, OrderCreated)
    consumer = PubSubConsumerSync(sync_pubsub_e2e, channel, OrderCreated, on_order)

    thread = threading.Thread(target=consumer.run, kwargs={"max_messages": 1})
    thread.start()
    time.sleep(0.1)
    producer.publish(OrderCreated(order_id=7, sku="E2E-SYNC"))
    thread.join(timeout=10.0)

    assert not thread.is_alive()
    assert received == [OrderCreated(order_id=7, sku="E2E-SYNC")]


def test_e2e_sync_producer_consumer_with_dependencies(
    sync_pubsub_e2e: RedisPubSubSyncAdapter,
) -> None:
    received: list[OrderCreated] = []
    db_calls: list[str] = []
    channel = f"orders-{uuid.uuid4().hex}"

    class FakeDb:
        def record(self, sku: str) -> None:
            db_calls.append(sku)

    db = FakeDb()

    def on_order(event: OrderCreated, db: FakeDb) -> None:
        db.record(event.sku)
        received.append(event)

    producer = PubSubProducerSync(sync_pubsub_e2e, channel, OrderCreated)
    consumer = PubSubConsumerSync(
        sync_pubsub_e2e,
        channel,
        OrderCreated,
        on_order,
        db=db,
    )

    thread = threading.Thread(target=consumer.run, kwargs={"max_messages": 1})
    thread.start()
    time.sleep(0.1)
    producer.publish(OrderCreated(order_id=99, sku="DEP"))
    thread.join(timeout=10.0)

    assert not thread.is_alive()
    assert received == [OrderCreated(order_id=99, sku="DEP")]
    assert db_calls == ["DEP"]


@pytest.mark.asyncio
async def test_e2e_async_producer_consumer(
    async_pubsub_e2e: RedisPubSubAsyncAdapter,
) -> None:
    received: list[OrderCreated] = []
    channel = f"orders-{uuid.uuid4().hex}"

    async def on_order(event: OrderCreated) -> None:
        received.append(event)

    producer = PubSubProducerAsync(async_pubsub_e2e, channel, OrderCreated)
    consumer = PubSubConsumerAsync(async_pubsub_e2e, channel, OrderCreated, on_order)

    task = asyncio.create_task(consumer.run(max_messages=1))
    await asyncio.sleep(0.1)
    await producer.publish(OrderCreated(order_id=42, sku="E2E-ASYNC"))
    await asyncio.wait_for(task, timeout=10.0)

    assert received == [OrderCreated(order_id=42, sku="E2E-ASYNC")]


@pytest.mark.asyncio
async def test_e2e_async_producer_consumer_with_dependencies(
    async_pubsub_e2e: RedisPubSubAsyncAdapter,
) -> None:
    received: list[OrderCreated] = []
    db_calls: list[str] = []
    channel = f"orders-{uuid.uuid4().hex}"

    class FakeDb:
        def record(self, sku: str) -> None:
            db_calls.append(sku)

    db = FakeDb()

    async def on_order(event: OrderCreated, db: FakeDb) -> None:
        db.record(event.sku)
        received.append(event)

    producer = PubSubProducerAsync(async_pubsub_e2e, channel, OrderCreated)
    consumer = PubSubConsumerAsync(
        async_pubsub_e2e,
        channel,
        OrderCreated,
        on_order,
        db=db,
    )

    task = asyncio.create_task(consumer.run(max_messages=1))
    await asyncio.sleep(0.1)
    await producer.publish(OrderCreated(order_id=100, sku="ASYNC-DEP"))
    await asyncio.wait_for(task, timeout=10.0)

    assert received == [OrderCreated(order_id=100, sku="ASYNC-DEP")]
    assert db_calls == ["ASYNC-DEP"]

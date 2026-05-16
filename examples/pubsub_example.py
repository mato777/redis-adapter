"""
Typed pub/sub: producer publishes Pydantic messages; consumer runs your handler.

Prerequisites
-------------
Redis running locally (or set ``REDIS_URL``), project installed (``uv sync``), then::

    REDIS_URL=redis://127.0.0.1:6379/0 uv run python examples/pubsub_example.py
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

from pydantic import BaseModel

from async_redis_client import (
    PubSubConsumerAsync,
    PubSubProducerAsync,
    RedisPubSubAsyncAdapter,
)

CHANNEL = "demo:events"


class OrderCreated(BaseModel):
    order_id: int
    sku: str


@dataclass
class FakeDb:
    """Stand-in for a DB session passed into the consumer handler."""

    rows: list[str] = field(default_factory=list)

    def save_order(self, sku: str) -> None:
        self.rows.append(sku)
        print(f"  db: saved order sku={sku!r}")


async def on_order_created(event: OrderCreated, db: FakeDb) -> None:
    print(f"handler: order_id={event.order_id} sku={event.sku!r}")
    db.save_order(event.sku)


async def main() -> None:
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    db = FakeDb()

    async with RedisPubSubAsyncAdapter.from_standalone_url(
        url, decode_responses=False
    ) as bus:
        producer = PubSubProducerAsync(bus, CHANNEL, OrderCreated)
        consumer = PubSubConsumerAsync(
            bus, CHANNEL, OrderCreated, on_order_created, db=db
        )

        stop = asyncio.Event()
        listener = asyncio.create_task(consumer.run(stop_event=stop))

        await asyncio.sleep(0.2)
        for order_id, sku in ((1, "WIDGET"), (2, "GADGET")):
            n = await producer.publish(OrderCreated(order_id=order_id, sku=sku))
            print(f"published order {order_id} -> {n} subscriber(s)")
            await asyncio.sleep(0.1)

        stop.set()
        await listener
        print("done; db rows:", db.rows)


if __name__ == "__main__":
    asyncio.run(main())

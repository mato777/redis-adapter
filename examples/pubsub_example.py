"""
Minimal async pub/sub: subscribe in a background task, publish from main.

Prerequisites
-------------
Redis running locally (or set ``REDIS_URL``), project installed (``uv sync``), then::

    REDIS_URL=redis://127.0.0.1:6379/0 uv run python examples/pubsub_example.py
"""

from __future__ import annotations

import asyncio
import os

from async_redis_client import PubSubAsyncPort, RedisPubSubAsyncAdapter

CHANNEL = "demo:events"


async def listen(bus: PubSubAsyncPort) -> None:
    sub = await bus.subscribe(CHANNEL)
    try:
        async for msg in sub.listen():
            print(f"received on {msg.channel!r}: {msg.data!r}")
            if msg.data == "done":
                break
    finally:
        await sub.close()


async def main() -> None:
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    async with RedisPubSubAsyncAdapter.from_standalone_url(
        url, decode_responses=True
    ) as bus:
        listener = asyncio.create_task(listen(bus))
        await asyncio.sleep(0.2)
        for text in ("hello", "world", "done"):
            n = await bus.publish(CHANNEL, text)
            print(f"published {text!r} -> {n} subscriber(s)")
            await asyncio.sleep(0.1)
        await listener


if __name__ == "__main__":
    asyncio.run(main())

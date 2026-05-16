"""
End-to-end pub/sub tests against Redis in Docker (`testcontainers[redis]`).

Requires a working Docker daemon. To skip locally: ``pytest -m "not e2e"``.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from testcontainers.redis import RedisContainer

from async_redis_client import RedisPubSubAsyncAdapter, RedisPubSubSyncAdapter

pytestmark = pytest.mark.e2e


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
    prefix = f"e2e-pub:{uuid.uuid4().hex}:"
    client = redis_container_session.get_client(decode_responses=True)
    adapter = RedisPubSubSyncAdapter(client, channel_prefix=prefix)
    yield adapter
    adapter.close()


@pytest.fixture()
async def async_pubsub_e2e(
    redis_container_session: RedisContainer,
) -> AsyncIterator[RedisPubSubAsyncAdapter]:
    prefix = f"e2e-pub:{uuid.uuid4().hex}:"
    adapter = RedisPubSubAsyncAdapter.from_standalone_url(
        redis_url(redis_container_session),
        channel_prefix=prefix,
        decode_responses=True,
    )
    try:
        yield adapter
    finally:
        await adapter.close()


def test_e2e_sync_pubsub_roundtrip(sync_pubsub_e2e: RedisPubSubSyncAdapter) -> None:
    sub = sync_pubsub_e2e.subscribe("notifications")
    try:
        sync_pubsub_e2e.publish("notifications", "e2e-sync")
        msg = sub.get_message(timeout=5.0)
        assert msg is not None
        assert msg.channel == "notifications"
        assert msg.data == "e2e-sync"
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_e2e_async_pubsub_roundtrip(
    async_pubsub_e2e: RedisPubSubAsyncAdapter,
) -> None:
    sub = await async_pubsub_e2e.subscribe("notifications")
    try:
        await async_pubsub_e2e.publish("notifications", "e2e-async")
        msg = await sub.get_message(timeout=5.0)
        assert msg is not None
        assert msg.channel == "notifications"
        assert msg.data == "e2e-async"
    finally:
        await sub.close()

from __future__ import annotations

import pytest

from async_redis_client import PubSubClosedError, RedisPubSubSyncAdapter


@pytest.fixture()
def sync_pubsub() -> RedisPubSubSyncAdapter:
    import fakeredis

    client = fakeredis.FakeRedis(decode_responses=True)
    return RedisPubSubSyncAdapter(client)


def test_sync_publish_and_receive(sync_pubsub: RedisPubSubSyncAdapter) -> None:
    sub = sync_pubsub.subscribe("events")
    try:
        receivers = sync_pubsub.publish("events", "hello")
        assert receivers >= 1
        msg = sub.get_message(timeout=2.0)
        assert msg is not None
        assert msg.channel == "events"
        assert msg.data == "hello"
    finally:
        sub.close()


def test_sync_channel_prefix() -> None:
    import fakeredis

    client = fakeredis.FakeRedis(decode_responses=True)
    adapter = RedisPubSubSyncAdapter(client, channel_prefix="demo:")
    sub = adapter.subscribe("alerts")
    try:
        adapter.publish("alerts", "ping")
        msg = sub.get_message(timeout=2.0)
        assert msg is not None
        assert msg.channel == "alerts"
    finally:
        sub.close()


def test_sync_listen_yields_messages(sync_pubsub: RedisPubSubSyncAdapter) -> None:
    sub = sync_pubsub.subscribe("stream")
    try:
        sync_pubsub.publish("stream", "one")
        sync_pubsub.publish("stream", "two")
        received: list[str | bytes] = []
        for msg in sub.listen():
            received.append(msg.data)
            if len(received) >= 2:
                break
        assert received == ["one", "two"]
    finally:
        sub.close()


def test_sync_closed_adapter_raises(sync_pubsub: RedisPubSubSyncAdapter) -> None:
    sync_pubsub.close()
    with pytest.raises(PubSubClosedError):
        sync_pubsub.publish("x", "y")

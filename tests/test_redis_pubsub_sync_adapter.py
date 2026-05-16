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


def test_sync_subscription_unsubscribe_and_close(
    sync_pubsub: RedisPubSubSyncAdapter,
) -> None:
    sub = sync_pubsub.subscribe("a", "b")
    try:
        sub.unsubscribe("a")
        sub.unsubscribe()
        sub.close()
        sub.close()
        with pytest.raises(PubSubClosedError):
            sub.get_message()
    finally:
        if not sub._closed:
            sub.close()


def test_sync_get_message_timeout_returns_none(
    sync_pubsub: RedisPubSubSyncAdapter,
) -> None:
    sub = sync_pubsub.subscribe("quiet")
    try:
        assert sub.get_message(timeout=0.01) is None
    finally:
        sub.close()


def test_sync_punsubscribe_with_and_without_patterns(
    sync_pubsub: RedisPubSubSyncAdapter,
) -> None:
    sub = sync_pubsub.psubscribe("evt*")
    try:
        sub.punsubscribe("evt*")
    finally:
        sub.close()

    sub_all = sync_pubsub.psubscribe("other*")
    try:
        sub_all.punsubscribe()
    finally:
        sub_all.close()


def test_sync_closed_subscription_raises(sync_pubsub: RedisPubSubSyncAdapter) -> None:
    sub = sync_pubsub.subscribe("x")
    sub.close()
    with pytest.raises(PubSubClosedError):
        sub.unsubscribe("x")


def test_sync_context_manager_and_owns_client_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fakeredis

    from async_redis_client.adapters.redis import pubsub_sync_adapter as mod

    fake = fakeredis.FakeRedis(decode_responses=True)
    closed: list[int] = []
    orig_close = fake.close

    def track_close() -> None:
        closed.append(1)
        orig_close()

    fake.close: object = track_close
    monkeypatch.setattr(mod.Redis, "from_url", lambda url, **kw: fake)

    adapter = RedisPubSubSyncAdapter.from_standalone_url("redis://localhost/8")
    with adapter as entered:
        assert entered is adapter
    assert closed == [1]
    adapter.close()
    assert closed == [1]


def test_sync_from_cluster_url(monkeypatch: pytest.MonkeyPatch) -> None:
    import fakeredis

    from async_redis_client.adapters.redis import pubsub_sync_adapter as mod

    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(mod.RedisCluster, "from_url", lambda url, **kw: fake)
    adapter = RedisPubSubSyncAdapter.from_cluster_url("redis://cluster/0")
    sub = adapter.subscribe("c")
    try:
        adapter.publish("c", "v")
        msg = sub.get_message(timeout=2.0)
        assert msg is not None
        assert msg.data == "v"
    finally:
        sub.close()
        adapter.close()


def test_sync_punsubscribe_with_pattern(sync_pubsub: RedisPubSubSyncAdapter) -> None:
    sub = sync_pubsub.psubscribe("evt*")
    try:
        sub.punsubscribe("evt*")
    finally:
        sub.close()

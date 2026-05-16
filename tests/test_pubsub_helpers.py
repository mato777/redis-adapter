from __future__ import annotations

from async_redis_client.adapters.redis._pubsub_helpers import (
    full_channel,
    logical_channel,
    parse_pubsub_message,
)


def test_full_and_logical_channel() -> None:
    assert full_channel("ns:", "events") == "ns:events"
    assert logical_channel("ns:", "ns:events") == "events"


def test_parse_message_and_pmessage() -> None:
    raw = {
        "type": "message",
        "pattern": None,
        "channel": "ns:events",
        "data": "hi",
    }
    msg = parse_pubsub_message(raw, channel_prefix="ns:")
    assert msg is not None
    assert msg.channel == "events"
    assert msg.data == "hi"
    assert msg.pattern is None

    raw_p = {
        "type": "pmessage",
        "pattern": "ns:evt*",
        "channel": "ns:events",
        "data": b"bytes",
    }
    pmsg = parse_pubsub_message(raw_p, channel_prefix="ns:")
    assert pmsg is not None
    assert pmsg.pattern == "evt*"
    assert pmsg.data == b"bytes"


def test_parse_ignores_subscribe_ack() -> None:
    assert (
        parse_pubsub_message(
            {"type": "subscribe", "channel": "c", "data": 1},
            channel_prefix="",
        )
        is None
    )

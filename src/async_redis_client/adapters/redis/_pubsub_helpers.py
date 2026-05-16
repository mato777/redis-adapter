from __future__ import annotations

from async_redis_client.pubsub_message import PubSubMessage


def full_channel(channel_prefix: str, channel: str) -> str:
    return f"{channel_prefix}{channel}"


def logical_channel(channel_prefix: str, physical: str) -> str:
    if channel_prefix and physical.startswith(channel_prefix):
        return physical[len(channel_prefix) :]
    return physical


def logical_pattern(channel_prefix: str, physical: str) -> str:
    return logical_channel(channel_prefix, physical)


def as_str(value: str | bytes) -> str:
    return value if isinstance(value, str) else value.decode()


def coerce_data(value: object) -> str | bytes:
    if isinstance(value, (str, bytes)):
        return value
    return str(value).encode()


def parse_pubsub_message(
    raw: dict | None,
    *,
    channel_prefix: str,
) -> PubSubMessage | None:
    if raw is None:
        return None
    kind = raw.get("type")
    if kind == "message":
        channel = logical_channel(channel_prefix, as_str(raw["channel"]))
        return PubSubMessage(channel=channel, data=coerce_data(raw["data"]))
    if kind == "pmessage":
        pattern = logical_pattern(channel_prefix, as_str(raw["pattern"]))
        channel = logical_channel(channel_prefix, as_str(raw["channel"]))
        return PubSubMessage(
            channel=channel,
            data=coerce_data(raw["data"]),
            pattern=pattern,
        )
    return None

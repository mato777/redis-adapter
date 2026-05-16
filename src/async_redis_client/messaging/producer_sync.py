from __future__ import annotations

from typing import Generic, TypeVar

from async_redis_client.messaging.codec import encode_message
from async_redis_client.ports.sync_pubsub_port import PubSubSyncPort

TMessage = TypeVar("TMessage")


class PubSubProducerSync(Generic[TMessage]):
    """
    Publish typed messages (Pydantic ``BaseModel`` or dataclass) on a Redis channel.

    Depends on :class:`~async_redis_client.ports.sync_pubsub_port.PubSubSyncPort` only.
    """

    __slots__ = ("_bus", "_channel", "_message_type")

    def __init__(
        self,
        bus: PubSubSyncPort,
        channel: str,
        message_type: type[TMessage],
    ) -> None:
        self._bus = bus
        self._channel = channel
        self._message_type = message_type

    def publish(self, message: TMessage) -> int:
        """Encode ``message`` as JSON and publish; returns Redis subscriber count."""
        payload = encode_message(message)
        return self._bus.publish(self._channel, payload)

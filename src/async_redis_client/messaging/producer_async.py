from __future__ import annotations

from typing import Generic, TypeVar

from async_redis_client.messaging.codec import encode_message
from async_redis_client.ports.async_pubsub_port import PubSubAsyncPort

TMessage = TypeVar("TMessage")


class PubSubProducerAsync(Generic[TMessage]):
    """
    Async producer: publish typed Pydantic or dataclass messages on a channel.
    """

    __slots__ = ("_bus", "_channel", "_message_type")

    def __init__(
        self,
        bus: PubSubAsyncPort,
        channel: str,
        message_type: type[TMessage],
    ) -> None:
        self._bus = bus
        self._channel = channel
        self._message_type = message_type

    async def publish(self, message: TMessage) -> int:
        payload = encode_message(message)
        return await self._bus.publish(self._channel, payload)

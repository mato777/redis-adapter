from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, TypeVar

from async_redis_client.messaging._invoke import (
    invoke_handler_sync,
    validate_handler_dependencies,
)
from async_redis_client.messaging.codec import decode_message
from async_redis_client.ports.sync_pubsub_port import PubSubSyncPort
from async_redis_client.schemas import PubSubMessage

TMessage = TypeVar("TMessage")


class PubSubConsumerSync(Generic[TMessage]):
    """
    Blocking consumer: decode messages and call a user ``handler``.

    Pass extra dependencies (database session, cache port, etc.) as keyword arguments
    to the constructor; they are forwarded to ``handler`` when the parameter names match.

    Example::

        def on_order(event: OrderCreated, db: Session) -> None:
            db.save(event)

        consumer = PubSubConsumerSync(
            bus, "orders", OrderCreated, on_order, db=session_factory()
        )
        consumer.run(max_messages=10)
    """

    __slots__ = ("_bus", "_channel", "_message_type", "_handler", "_dependencies")

    def __init__(
        self,
        bus: PubSubSyncPort,
        channel: str,
        message_type: type[TMessage],
        handler: Callable[..., Any],
        **dependencies: Any,
    ) -> None:
        self._bus = bus
        self._channel = channel
        self._message_type = message_type
        self._handler = handler
        self._dependencies = dependencies
        validate_handler_dependencies(handler, dependencies)

    def run(self, *, max_messages: int | None = None) -> None:
        """Subscribe and invoke ``handler`` for each message until ``max_messages`` or forever."""
        sub = self._bus.subscribe(self._channel)
        count = 0
        try:
            for envelope in sub.listen():
                self._dispatch(envelope)
                count += 1
                if max_messages is not None and count >= max_messages:
                    break
        finally:
            sub.close()

    def _dispatch(self, envelope: PubSubMessage) -> None:
        message = decode_message(self._message_type, envelope.data)
        invoke_handler_sync(self._handler, message, self._dependencies)

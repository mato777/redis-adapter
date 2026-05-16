from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from async_redis_client.messaging._invoke import (
    invoke_handler_async,
    validate_handler_dependencies,
)
from async_redis_client.messaging.codec import decode_message
from async_redis_client.ports.async_pubsub_port import PubSubAsyncPort
from async_redis_client.schemas import PubSubMessage

TMessage = TypeVar("TMessage")


class PubSubConsumerAsync(Generic[TMessage]):
    """
    Async consumer with dependency injection for handler parameters (``db``, etc.).

    Handlers may be sync or async. Use :meth:`run` in a task; cancel the task, set
    ``max_messages``, or set ``stop_event`` to stop.
    """

    __slots__ = ("_bus", "_channel", "_message_type", "_handler", "_dependencies")

    def __init__(
        self,
        bus: PubSubAsyncPort,
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

    async def run(
        self,
        *,
        max_messages: int | None = None,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """
        Listen on ``channel`` and dispatch to ``handler``.

        When ``stop_event`` is set, polling uses short timeouts so shutdown is responsive.
        """
        sub = await self._bus.subscribe(self._channel)
        count = 0
        try:
            if stop_event is None:
                async for envelope in sub.listen():
                    await self._dispatch(envelope)
                    count += 1
                    if max_messages is not None and count >= max_messages:
                        break
            else:
                while not stop_event.is_set():
                    envelope = await sub.get_message(timeout=0.5)
                    if envelope is None:
                        continue
                    await self._dispatch(envelope)
                    count += 1
                    if max_messages is not None and count >= max_messages:
                        break
        finally:
            await sub.close()

    async def _dispatch(self, envelope: PubSubMessage) -> None:
        message = decode_message(self._message_type, envelope.data)
        await invoke_handler_async(self._handler, message, self._dependencies)

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PubSubMessage:
    """A Redis pub/sub payload delivered to subscribers."""

    channel: str
    data: str | bytes
    pattern: str | None = None

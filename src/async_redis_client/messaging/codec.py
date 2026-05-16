from __future__ import annotations

from dataclasses import is_dataclass
from typing import TypeVar

from pydantic import BaseModel, TypeAdapter

from async_redis_client.errors import SerializationError

TMessage = TypeVar("TMessage")


def encode_message(message: object) -> bytes:
    """Serialize a Pydantic model or dataclass to UTF-8 JSON bytes for Redis pub/sub."""
    if isinstance(message, BaseModel):
        return message.model_dump_json().encode("utf-8")
    if is_dataclass(message) and not isinstance(message, type):
        return TypeAdapter(type(message)).dump_json(message)
    raise TypeError(
        "message must be a Pydantic BaseModel instance or dataclass instance; "
        f"got {type(message)!r}"
    )


def decode_message(message_type: type[TMessage], data: str | bytes) -> TMessage:
    """Deserialize UTF-8 JSON bytes into ``message_type`` (Pydantic model or dataclass)."""
    raw = data if isinstance(data, bytes) else data.encode("utf-8")
    try:
        return TypeAdapter(message_type).validate_json(raw)
    except Exception as exc:
        raise SerializationError(
            f"Pub/sub payload failed validation as {message_type!r}."
        ) from exc

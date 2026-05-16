from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import BaseModel

from async_redis_client.errors import SerializationError
from async_redis_client.messaging.codec import decode_message, encode_message


class EventModel(BaseModel):
    id: int
    label: str


@dataclass(frozen=True, slots=True)
class EventDataclass:
    id: int
    label: str


def test_encode_decode_pydantic() -> None:
    raw = encode_message(EventModel(id=1, label="a"))
    got = decode_message(EventModel, raw)
    assert got == EventModel(id=1, label="a")


def test_encode_decode_dataclass() -> None:
    raw = encode_message(EventDataclass(id=2, label="b"))
    got = decode_message(EventDataclass, raw)
    assert got == EventDataclass(id=2, label="b")


def test_encode_rejects_plain_object() -> None:
    with pytest.raises(TypeError):
        encode_message({"x": 1})  # type: ignore[arg-type]


def test_decode_invalid_json_raises() -> None:
    with pytest.raises(SerializationError):
        decode_message(EventModel, b"not-json")

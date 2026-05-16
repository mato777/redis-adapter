from __future__ import annotations

import pytest
from pydantic import BaseModel

from async_redis_client import SerializationError
from async_redis_client.serialization import (
    dump_json_value,
    dump_model,
    load_as_type,
    load_json_value,
)


class Widget(BaseModel):
    name: str


def test_dump_json_value_roundtrip() -> None:
    payload = dump_json_value({"n": 1, "tags": ["a"]})
    assert load_json_value(payload) == {"n": 1, "tags": ["a"]}


def test_dump_json_value_non_serializable_raises() -> None:
    with pytest.raises(SerializationError, match="not JSON-serializable"):
        dump_json_value(object())  # type: ignore[arg-type]


def test_load_json_value_invalid_payload_raises() -> None:
    with pytest.raises(SerializationError, match="failed validation after decrypt"):
        load_json_value(b"not-json")


def test_dump_model_and_load_as_type() -> None:
    model = Widget(name="gear")
    data = dump_model(model)
    loaded = load_as_type(Widget, data)
    assert isinstance(loaded, Widget)
    assert loaded.name == "gear"


def test_load_as_type_validation_error_raises() -> None:
    with pytest.raises(SerializationError, match="Model payload failed validation"):
        load_as_type(Widget, b'{"name": 123}')

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, JsonValue, TypeAdapter, ValidationError

from async_redis_client.errors import SerializationError

TModel = TypeVar("TModel")

_json_adapter = TypeAdapter(JsonValue)


def dump_json_value(value: JsonValue) -> bytes:
    """Serialize a JSON-compatible tree to UTF-8 JSON bytes (strict JSON semantics)."""
    try:
        return _json_adapter.dump_json(value)
    except (ValidationError, ValueError) as exc:
        raise SerializationError(
            "Value is not JSON-serializable under strict rules."
        ) from exc


def load_json_value(data: bytes) -> JsonValue:
    try:
        return _json_adapter.validate_json(data)
    except ValidationError as exc:
        raise SerializationError(
            "JSON payload failed validation after decrypt."
        ) from exc


def dump_model(model: BaseModel) -> bytes:
    return model.model_dump_json().encode("utf-8")


def load_as_type(typ: type[TModel], data: bytes) -> TModel:
    """Hydrate ``typ`` from UTF-8 JSON bytes using Pydantic v2 validation."""
    try:
        return TypeAdapter(typ).validate_json(data)
    except ValidationError as exc:
        raise SerializationError(
            "Model payload failed validation after decrypt."
        ) from exc

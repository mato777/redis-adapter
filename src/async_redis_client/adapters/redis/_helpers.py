from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from cryptography.fernet import Fernet
from pydantic import JsonValue

from async_redis_client.crypto import decrypt_bytes, encrypt_bytes
from async_redis_client.serialization import dump_json_value, load_json_value


def full_key(namespace: str, key_prefix: str, logical_key: str) -> str:
    """Physical Redis key: ``namespace + key_prefix + logical_key``."""
    return f"{namespace}{key_prefix}{logical_key}"


def redis_raw_to_bytes(raw: object) -> bytes:
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, bytearray):
        return bytes(raw)
    return bytes(raw)


def encrypt_json_tree(fernet: Fernet, value: JsonValue) -> bytes:
    return encrypt_bytes(fernet, dump_json_value(value))


def decrypt_json_tree(
    fernet: Fernet,
    raw: bytes,
    *,
    secondary: Fernet | None,
) -> JsonValue:
    plain = decrypt_bytes(fernet, raw, secondary=secondary)
    return load_json_value(plain)


def pipeline_enqueue_json_sets(
    pipe: Any,
    mapping: Mapping[str, JsonValue],
    *,
    namespace: str,
    key_prefix: str,
    fernet: Fernet,
    ttl_seconds: int | None,
) -> None:
    for logical_key, value in mapping.items():
        fk = full_key(namespace, key_prefix, logical_key)
        blob = encrypt_json_tree(fernet, value)
        if ttl_seconds is not None:
            pipe.set(fk, blob, ex=ttl_seconds)
        else:
            pipe.set(fk, blob)


def redis_keys_from_logical(
    namespace: str, key_prefix: str, keys: Sequence[str]
) -> list[str]:
    return [full_key(namespace, key_prefix, k) for k in keys]


def decode_mget_json_rows(
    keys: Sequence[str],
    values: Sequence[object | None],
    *,
    fernet: Fernet,
    secondary: Fernet | None,
) -> dict[str, JsonValue | None]:
    out: dict[str, JsonValue | None] = {}
    for logical, raw in zip(keys, values, strict=False):
        if raw is None:
            out[logical] = None
            continue
        data = redis_raw_to_bytes(raw)
        out[logical] = decrypt_json_tree(fernet, data, secondary=secondary)
    return out

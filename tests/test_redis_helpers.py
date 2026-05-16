from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

from async_redis_client.adapters.redis._helpers import (
    decode_mget_json_rows,
    decrypt_json_tree,
    encrypt_json_tree,
    full_key,
    pipeline_enqueue_json_sets,
    redis_keys_from_logical,
    redis_raw_to_bytes,
)


@pytest.fixture()
def fernet() -> Fernet:
    return Fernet(Fernet.generate_key())


def test_full_key_and_redis_keys_from_logical() -> None:
    assert full_key("ns:", "pre:", "k") == "ns:pre:k"
    assert redis_keys_from_logical("ns:", "pre:", ["a", "b"]) == [
        "ns:pre:a",
        "ns:pre:b",
    ]


def test_redis_raw_to_bytes_coerces_types() -> None:
    assert redis_raw_to_bytes(b"abc") == b"abc"
    assert redis_raw_to_bytes(bytearray(b"abc")) == b"abc"
    assert redis_raw_to_bytes(memoryview(b"abc")) == b"abc"


def test_encrypt_decrypt_json_tree(fernet: Fernet) -> None:
    value = {"x": [1, None], "y": "z"}
    token = encrypt_json_tree(fernet, value)
    assert decrypt_json_tree(fernet, token, secondary=None) == value


def test_pipeline_enqueue_json_sets_with_and_without_ttl(fernet: Fernet) -> None:
    pipe = MagicMock()
    pipeline_enqueue_json_sets(
        pipe,
        {"a": 1, "b": {"z": 2}},
        namespace="n:",
        key_prefix="p:",
        fernet=fernet,
        ttl_seconds=30,
    )
    assert pipe.set.call_count == 2
    first_call = pipe.set.call_args_list[0]
    assert first_call.args[0] == "n:p:a"
    assert isinstance(first_call.args[1], bytes)
    assert first_call.kwargs == {"ex": 30}

    pipe.reset_mock()
    pipeline_enqueue_json_sets(
        pipe,
        {"only": True},
        namespace="",
        key_prefix="",
        fernet=fernet,
        ttl_seconds=None,
    )
    pipe.set.assert_called_once()
    assert pipe.set.call_args.kwargs == {}


def test_decode_mget_json_rows(fernet: Fernet) -> None:
    blob = encrypt_json_tree(fernet, {"ok": True})
    out = decode_mget_json_rows(
        ["hit", "miss", "raw"],
        [blob, None, bytearray(blob)],
        fernet=fernet,
        secondary=None,
    )
    assert out["hit"] == {"ok": True}
    assert out["miss"] is None
    assert out["raw"] == {"ok": True}

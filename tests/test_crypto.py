from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from async_redis_client import DecryptionError
from async_redis_client.crypto import (
    build_secondary_fernet,
    decrypt_bytes,
    encrypt_bytes,
)


def test_decrypt_bytes_primary_succeeds_secondary_unused() -> None:
    primary = Fernet(Fernet.generate_key())
    secondary = Fernet(Fernet.generate_key())
    token = encrypt_bytes(primary, b"hello")
    assert decrypt_bytes(primary, token, secondary=secondary) == b"hello"


def test_decrypt_bytes_fallback_to_secondary() -> None:
    primary = Fernet(Fernet.generate_key())
    secondary = Fernet(Fernet.generate_key())
    token = encrypt_bytes(secondary, b"legacy")
    assert decrypt_bytes(primary, token, secondary=secondary) == b"legacy"


def test_decrypt_bytes_no_secondary_raises() -> None:
    primary = Fernet(Fernet.generate_key())
    other = Fernet(Fernet.generate_key())
    token = encrypt_bytes(other, b"x")
    with pytest.raises(DecryptionError):
        decrypt_bytes(primary, token, secondary=None)


def test_decrypt_bytes_both_keys_fail() -> None:
    primary = Fernet(Fernet.generate_key())
    secondary = Fernet(Fernet.generate_key())
    other = Fernet(Fernet.generate_key())
    token = encrypt_bytes(other, b"x")
    with pytest.raises(DecryptionError):
        decrypt_bytes(primary, token, secondary=secondary)


def test_build_secondary_fernet_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    sec = Fernet.generate_key()
    monkeypatch.delenv("CACHE_FERNET_KEY_SECONDARY", raising=False)
    monkeypatch.setenv("CACHE_FERNET_KEY_SECONDARY", sec.decode("ascii"))
    f = build_secondary_fernet()
    assert f is not None
    assert f.decrypt(encrypt_bytes(f, b"e")) == b"e"


def test_build_secondary_fernet_explicit_overrides_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a = Fernet.generate_key()
    b = Fernet.generate_key()
    monkeypatch.setenv("CACHE_FERNET_KEY_SECONDARY", a.decode("ascii"))
    f = build_secondary_fernet(fernet_key=b)
    assert f is not None
    assert f.decrypt(encrypt_bytes(Fernet(b), b"z")) == b"z"

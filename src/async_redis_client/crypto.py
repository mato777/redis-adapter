from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken

from async_redis_client.errors import CacheError, DecryptionError


def load_fernet_key_from_env(env_var: str = "CACHE_FERNET_KEY") -> bytes | None:
    raw = os.environ.get(env_var)
    return raw.encode("ascii") if raw else None


def build_fernet(
    *, fernet_key: bytes | None, env_var: str = "CACHE_FERNET_KEY"
) -> Fernet:
    """Resolve a Fernet instance; explicit ``fernet_key`` wins over env."""
    key = fernet_key if fernet_key is not None else load_fernet_key_from_env(env_var)
    if key is None:
        msg = (
            "Missing Fernet key: pass fernet_key to the adapter "
            f"or set the {env_var} environment variable."
        )
        raise CacheError(msg)
    return Fernet(key)


def build_fernet_optional(*, fernet_key: bytes | None, env_var: str) -> Fernet | None:
    """Like :func:`build_fernet` but returns ``None`` if no key is provided and env is unset."""
    key = fernet_key if fernet_key is not None else load_fernet_key_from_env(env_var)
    if key is None:
        return None
    return Fernet(key)


def build_secondary_fernet(*, fernet_key: bytes | None = None) -> Fernet | None:
    """Previous / rotating key from ``fernet_key`` or env ``CACHE_FERNET_KEY_SECONDARY``."""
    return build_fernet_optional(
        fernet_key=fernet_key, env_var="CACHE_FERNET_KEY_SECONDARY"
    )


def encrypt_bytes(fernet: Fernet, plaintext: bytes) -> bytes:
    return fernet.encrypt(plaintext)


def decrypt_bytes(
    primary: Fernet,
    token: bytes,
    *,
    secondary: Fernet | None = None,
) -> bytes:
    """
    Decrypt with ``primary``; on failure, retry with ``secondary`` when given (key rotation).

    New writes should use the primary key only; the secondary accepts ciphertext produced
    with the previous key until data is re-encrypted.
    """
    try:
        return primary.decrypt(token)
    except InvalidToken:
        pass
    if secondary is not None:
        try:
            return secondary.decrypt(token)
        except InvalidToken as exc:
            raise DecryptionError(
                "Fernet decryption failed; token may be corrupt or encrypted with another key."
            ) from exc
    raise DecryptionError(
        "Fernet decryption failed; token may be corrupt or encrypted with another key."
    )

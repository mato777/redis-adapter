"""Stable cache- and pub/sub-related exceptions for adapters and domain code."""


class CacheError(Exception):
    """Base error for cache operations (configuration, corrupted payloads, etc.)."""


class PubSubError(Exception):
    """Base error for pub/sub operations."""


class PubSubClosedError(PubSubError):
    """Raised when a pub/sub operation runs after the adapter or subscription is closed."""


class PubSubSerializationError(PubSubError):
    """Raised when a pub/sub payload fails Pydantic/dataclass JSON validation."""


class CacheClosedError(CacheError):
    """Raised when a cache operation runs after the adapter has been closed."""


class CacheKeyNotFoundError(CacheError):
    """Raised when a required cache key has no stored JSON payload."""

    key: str

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Cache key not found: {key!r}")


class DecryptionError(CacheError):
    """Raised when Fernet decryption fails (wrong key, truncated or tampered blob)."""


class SerializationError(CacheError):
    """Raised when JSON/model validation fails after cache decrypt."""

"""Stable cache-related exceptions for adapters and optional domain handling."""


class CacheError(Exception):
    """Base error for cache operations (configuration, corrupted payloads, etc.)."""


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
    """Raised when JSON/model validation fails after decrypt."""

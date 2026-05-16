"""Backward-compatible re-exports; prefer ``sync_cache_port`` / ``async_cache_port``."""

from async_redis_client.ports.async_cache_port import CacheAsyncPort
from async_redis_client.ports.sync_cache_port import CacheSyncPort

__all__ = ["CacheAsyncPort", "CacheSyncPort"]

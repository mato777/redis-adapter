"""
Ports-and-adapters cache library: Redis-backed adapters with Fernet + Pydantic JSON.

Application code should depend on :class:`~async_redis_client.ports.sync_cache_port.CacheSyncPort`
or :class:`~async_redis_client.ports.async_cache_port.CacheAsyncPort` only; compose Redis adapters
in your bootstrap layer.
"""

from async_redis_client.adapters.memory import (
    MemoryCacheAsyncAdapter,
    MemoryCacheSyncAdapter,
)
from async_redis_client.adapters.redis import (
    RedisCacheAsyncAdapter,
    RedisCacheSyncAdapter,
)
from async_redis_client.errors import (
    CacheClosedError,
    CacheError,
    CacheKeyNotFoundError,
    DecryptionError,
    SerializationError,
)
from async_redis_client.ports.async_cache_port import CacheAsyncPort
from async_redis_client.ports.sync_cache_port import CacheSyncPort

SyncCachePort = CacheSyncPort
AsyncCachePort = CacheAsyncPort

__all__ = [
    "AsyncCachePort",
    "CacheAsyncPort",
    "CacheClosedError",
    "CacheError",
    "CacheKeyNotFoundError",
    "CacheSyncPort",
    "DecryptionError",
    "MemoryCacheAsyncAdapter",
    "MemoryCacheSyncAdapter",
    "RedisCacheAsyncAdapter",
    "RedisCacheSyncAdapter",
    "SerializationError",
    "SyncCachePort",
]

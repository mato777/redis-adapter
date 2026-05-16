"""
Ports-and-adapters cache and pub/sub library: Redis-backed adapters with Fernet + Pydantic JSON.

Application code should depend on cache ports
(:class:`~async_redis_client.ports.sync_cache_port.CacheSyncPort`,
:class:`~async_redis_client.ports.async_cache_port.CacheAsyncPort`) and pub/sub ports
(:class:`~async_redis_client.ports.sync_pubsub_port.PubSubSyncPort`,
:class:`~async_redis_client.ports.async_pubsub_port.PubSubAsyncPort`) only; compose Redis
adapters in your bootstrap layer.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("async-redis-client")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

from async_redis_client.adapters.memory import (
    MemoryCacheAsyncAdapter,
    MemoryCacheSyncAdapter,
    MemoryPubSubAsyncAdapter,
    MemoryPubSubSyncAdapter,
)
from async_redis_client.adapters.redis import (
    RedisCacheAsyncAdapter,
    RedisCacheSyncAdapter,
    RedisPubSubAsyncAdapter,
    RedisPubSubSyncAdapter,
)
from async_redis_client.errors import (
    CacheClosedError,
    CacheError,
    CacheKeyNotFoundError,
    DecryptionError,
    PubSubClosedError,
    PubSubError,
    PubSubSerializationError,
    SerializationError,
)
from async_redis_client.messaging import (
    PubSubConsumerAsync,
    PubSubConsumerSync,
    PubSubProducerAsync,
    PubSubProducerSync,
)
from async_redis_client.ports.async_cache_port import CacheAsyncPort
from async_redis_client.ports.async_pubsub_port import (
    PubSubAsyncPort,
    PubSubSubscriptionAsyncPort,
)
from async_redis_client.ports.sync_cache_port import CacheSyncPort
from async_redis_client.ports.sync_pubsub_port import (
    PubSubSubscriptionSyncPort,
    PubSubSyncPort,
)
from async_redis_client.schemas import PubSubMessage

SyncCachePort = CacheSyncPort
AsyncCachePort = CacheAsyncPort
SyncPubSubPort = PubSubSyncPort
AsyncPubSubPort = PubSubAsyncPort

__all__ = [
    "__version__",
    "AsyncCachePort",
    "AsyncPubSubPort",
    "CacheAsyncPort",
    "CacheClosedError",
    "CacheError",
    "CacheKeyNotFoundError",
    "CacheSyncPort",
    "DecryptionError",
    "MemoryCacheAsyncAdapter",
    "MemoryCacheSyncAdapter",
    "MemoryPubSubAsyncAdapter",
    "MemoryPubSubSyncAdapter",
    "PubSubAsyncPort",
    "PubSubConsumerAsync",
    "PubSubConsumerSync",
    "PubSubClosedError",
    "PubSubError",
    "PubSubSerializationError",
    "PubSubMessage",
    "PubSubProducerAsync",
    "PubSubProducerSync",
    "PubSubSubscriptionAsyncPort",
    "PubSubSubscriptionSyncPort",
    "PubSubSyncPort",
    "RedisCacheAsyncAdapter",
    "RedisCacheSyncAdapter",
    "RedisPubSubAsyncAdapter",
    "RedisPubSubSyncAdapter",
    "SerializationError",
    "SyncCachePort",
    "SyncPubSubPort",
]

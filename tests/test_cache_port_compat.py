from __future__ import annotations

import async_redis_client.ports.cache_port as cache_port
from async_redis_client.ports import async_cache_port, sync_cache_port
from async_redis_client.ports.cache_port import CacheAsyncPort, CacheSyncPort


def test_cache_port_reexports_sync_and_async_ports() -> None:
    assert CacheSyncPort is sync_cache_port.CacheSyncPort
    assert CacheAsyncPort is async_cache_port.CacheAsyncPort
    assert cache_port.__all__ == ["CacheAsyncPort", "CacheSyncPort"]

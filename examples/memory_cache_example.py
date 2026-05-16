"""
In-memory adapters for tests and local runs without Redis.

MemoryCacheSyncAdapter / MemoryCacheAsyncAdapter implement the same port methods as the Redis
adapters, but storage is process-local and TTL arguments are ignored.

No Docker is required for this script::

    uv run python examples/memory_cache_example.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_src = _REPO_ROOT / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from pydantic import BaseModel  # noqa: E402

from async_redis_client import (  # noqa: E402
    MemoryCacheAsyncAdapter,
    MemoryCacheSyncAdapter,
)


class Item(BaseModel):
    sku: str
    qty: int


def sync_demo() -> None:
    # Domain code can depend on CacheSyncPort and receive this implementation in tests.
    cache = MemoryCacheSyncAdapter(key_prefix="demo:")
    cache.set_json("cart", {"lines": []})
    cache.set_model("item:42", Item(sku="ABC", qty=2))
    print("sync get_json:", cache.get_json("cart"))
    print("sync get_as_model:", cache.get_as_model("item:42", Item))


async def async_demo() -> None:
    cache = MemoryCacheAsyncAdapter(key_prefix="demo:")
    await cache.set_json("note", {"text": "async façade uses a lock"})
    print("async get_json:", await cache.get_json("note"))


def main() -> None:
    sync_demo()
    asyncio.run(async_demo())


if __name__ == "__main__":
    main()

"""
Async Redis cache: RedisCacheAsyncAdapter.

Same semantics as the sync adapter (Fernet + JSON / models vs plaintext counters).

Prerequisites
-------------
Start Redis (see examples/Dockerfile), install the project (`uv sync`), then::

    REDIS_URL=redis://127.0.0.1:6379/0 uv run python examples/async_redis_example.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_src = _REPO_ROOT / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from cryptography.fernet import Fernet  # noqa: E402

from async_redis_client import CacheAsyncPort, RedisCacheAsyncAdapter  # noqa: E402


async def run_demo(cache: CacheAsyncPort) -> None:
    await cache.set_json("async:hello", {"message": "world"})
    got = await cache.get_json("async:hello")
    print("get_json:", got)

    await cache.set_many({"async:k1": "v1", "async:k2": "v2"}, ttl_seconds=60)
    many = await cache.get_many(["async:k1", "async:k2"])
    print("get_many:", many)

    total = await cache.incrby("counter:async_demo", 3)
    print("incrby:", total)


async def main() -> None:
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    env_key = os.environ.get("CACHE_FERNET_KEY")
    fernet_key = env_key.encode("ascii") if env_key else Fernet.generate_key()

    # Adapter owns the asyncio Redis client; async with closes it reliably.
    async with RedisCacheAsyncAdapter.from_standalone_url(
        url,
        fernet_key=fernet_key,
        key_prefix="{examples}:async:",
        decode_responses=False,
    ) as cache:
        await run_demo(cache)


if __name__ == "__main__":
    asyncio.run(main())

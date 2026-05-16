"""
Synchronous Redis cache: RedisCacheSyncAdapter + CacheSyncPort-style usage.

Prerequisites
-------------
1. Start Redis using the Dockerfile in this folder::

       docker build -f examples/Dockerfile -t async-redis-client-examples-redis examples/
       docker run --rm -p 6379:6379 async-redis-client-examples-redis

2. Install this project (from repo root)::

       uv sync

3. Run this script::

       REDIS_URL=redis://127.0.0.1:6379/0 uv run python examples/sync_redis_example.py

Environment
-----------
REDIS_URL
    Connection URL for standalone Redis (default: redis://127.0.0.1:6379/0).

CACHE_FERNET_KEY / CACHE_FERNET_KEY_SECONDARY
    Optional. If unset, this example generates a random primary Fernet key in-process
    (fine for a demo; in production configure keys via env or secrets).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow `python examples/sync_redis_example.py` when the package isn't installed yet:
_REPO_ROOT = Path(__file__).resolve().parents[1]
_src = _REPO_ROOT / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from cryptography.fernet import Fernet  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from redis import Redis  # noqa: E402

from async_redis_client import CacheSyncPort, RedisCacheSyncAdapter  # noqa: E402


class User(BaseModel):
    """Example domain model stored via set_model / get_as_model."""

    id: int
    name: str


def demo_url_factory(url: str, fernet_key: bytes) -> None:
    """
    Preferred bootstrap when this adapter should own the Redis client.

    decode_responses=False keeps values as bytes at the Redis layer; the adapter handles Fernet.
    """
    # Hash tag in key_prefix keeps logical keys in one slot if you later move to Redis Cluster.
    key_prefix = "{examples}:"
    with RedisCacheSyncAdapter.from_standalone_url(
        url,
        fernet_key=fernet_key,
        key_prefix=key_prefix,
        decode_responses=False,
    ) as cache:
        run_demo(cache)


def demo_injected_client(url: str, fernet_key: bytes) -> None:
    """
    Alternative: construct redis.Redis yourself (composition root) and inject it.

    owns_client=False means you must close the Redis client when the process shuts down.
    """
    client = Redis.from_url(url, decode_responses=False)
    try:
        cache = RedisCacheSyncAdapter(
            client,
            fernet_key=fernet_key,
            key_prefix="{examples}:",
            owns_client=False,
        )
        run_demo(cache)
    finally:
        client.close()


def run_demo(cache: CacheSyncPort) -> None:
    # --- JSON values (encrypted at rest as Fernet blobs of UTF-8 JSON) ---
    cache.set_json(
        "feature:demo", {"enabled": True, "tags": ["alpha"]}, ttl_seconds=120
    )
    payload = cache.get_json("feature:demo")
    print("get_json(feature:demo):", payload)

    # Missing keys return None on get_json; use get_json_or_raise_if_missing when you expect data.
    print("get_json(missing):", cache.get_json("no-such-key"))

    # --- Batch writes / reads (pipeline + MGET semantics) ---
    # On Redis Cluster, all logical keys must share the same hash slot (hash tags help).
    cache.set_many({"batch:a": 1, "batch:b": 2}, ttl_seconds=None)
    print("get_many:", cache.get_many(["batch:a", "batch:b", "batch:missing"]))

    # --- Pydantic models (distinct Redis encoding from plain JSON trees) ---
    user = User(id=1, name="Ada")
    cache.set_model("user:1", user, ttl_seconds=3600)
    loaded = cache.get_as_model("user:1", User)
    print("get_as_model(user:1):", loaded)

    # --- Plaintext integer counters (do not mix with encrypted JSON under the same key) ---
    counter_key = "counter:demo_requests"
    n = cache.incrby(counter_key, 1)
    print("incrby counter:", n)

    cache.delete("feature:demo")
    print("exists after delete:", cache.exists("feature:demo"))


def main() -> None:
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

    # Primary Fernet key: demo generates one if env doesn't provide CACHE_FERNET_KEY.
    env_key = os.environ.get("CACHE_FERNET_KEY")
    fernet_key = env_key.encode("ascii") if env_key else Fernet.generate_key()

    print("Using REDIS_URL:", url)
    print("--- URL factory (adapter owns client) ---")
    demo_url_factory(url, fernet_key)
    print("--- Injected Redis client (you own lifecycle) ---")
    demo_injected_client(url, fernet_key)


if __name__ == "__main__":
    main()

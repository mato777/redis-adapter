# async-redis-client

A small **Ports and Adapters (hexagonal)** cache library for Python: application code depends on **`CacheSyncPort` / `CacheAsyncPort`** (`typing.Protocol`); **Redis** (sync or asyncio) **or an in-memory implementation** satisfies those protocols behind the scenes.

**Features:**

- Sync and async Redis adapters built on **[redis-py](https://redis.readthedocs.io/)** (`Redis`, `RedisCluster`, and asyncio equivalents)—inject a client from your composition root, or use **`from_standalone_url`** / **`from_cluster_url`**.
- **Fernet encryption** at rest for cached values; payloads are **UTF-8 JSON** via **Pydantic v2** (`JsonValue`, `BaseModel`, `TypeAdapter`).
- **Optional secondary Fernet key** for decryption during rotation (`CACHE_FERNET_KEY_SECONDARY` or constructor arg); writes always use the primary key.
- **Plaintext integer counters** (`incr`, `decr`, `incrby`)—keep counter keys separate from encrypted JSON keys (for example a `counter:` prefix).
- **`set_many` / `get_many`** via pipeline/`MGET` semantics—on **Redis Cluster**, keys must land in the **same hash slot** (use hash tags in keys or `key_prefix`, e.g. `{tenant}:item:1`).
- **Memory adapters** for fast tests and local use (`MemoryCacheSyncAdapter`, `MemoryCacheAsyncAdapter`).

Requirements: **Python ≥ 3.11**, **redis-py ≥ 7.4** (stable `redis` on PyPI), **cryptography**, **pydantic ≥ 2**. Example and e2e Docker images use **Redis 8** server (`redis:8-alpine`).

## Install

**PyPI distribution name:** `async-redis-client`  
**Import name:** `async_redis_client`

### In another project (uv)

From Git (pin a tag or commit for reproducibility):

```bash
uv add "async-redis-client @ git+https://github.com/mato777/redis-adapter.git"
```

From a local checkout (editable, good for monorepos):

```bash
uv add --editable /path/to/async-redis-client
```

Then import the public API:

```python
from async_redis_client import CacheSyncPort, RedisCacheSyncAdapter
```

### pip / wheel

```bash
pip install "async-redis-client @ git+https://github.com/mato777/redis-adapter.git"
# or, from a clone:
pip install .
```

### Develop this repo

Using [uv](https://docs.astral.sh/uv/) (recommended; `uv.lock` is in-repo):

```bash
git clone https://github.com/mato777/redis-adapter.git
cd redis-adapter
uv sync
uv run pytest
```

`uv sync` installs the package in editable mode so `import async_redis_client` works immediately.

## Configuration

| Setting | Meaning |
|---------|---------|
| **`CACHE_FERNET_KEY`** | URL-safe base64 Fernet key (ASCII). Used when `fernet_key` is omitted in the adapter constructor. |
| **`CACHE_FERNET_KEY_SECONDARY`** | Optional legacy key tried on decrypt after primary fails (rotation). Constructor `fernet_key_secondary` overrides. |
| **`key_prefix`** (constructor) | Optional string prepended to logical keys on Redis adapters. |

Generate a Fernet key (store securely in production):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Usage

Depend on **`CacheSyncPort`** or **`CacheAsyncPort`** in your domain/services; compose a Redis or memory adapter in bootstrap.

### Sync Redis (inject client)

```python
from redis import Redis
from async_redis_client import CacheSyncPort, RedisCacheSyncAdapter


def bootstrap_cache() -> CacheSyncPort:
    client = Redis.from_url("redis://localhost:6379/0", decode_responses=False)
    # owns_client=False (default): you must client.close() when finished.
    return RedisCacheSyncAdapter(client, key_prefix="{myapp}")  # CLUSTER_FRIENDLY PREFIX EXAMPLE


cache = bootstrap_cache()

cache.set_json("feature:toggle", {"enabled": True}, ttl_seconds=60)
payload = cache.get_json("feature:toggle")

cache.incrby("counter:requests", 1)  # plaintext integer counter
# cache.close() is a no-op here; close the Redis client from your composition root.
```

### Sync Redis (URL factory)

```python
from async_redis_client import RedisCacheSyncAdapter

with RedisCacheSyncAdapter.from_standalone_url(
    "redis://localhost:6379/0",
    key_prefix="{myapp}:",
) as cache:
    cache.set_many({"a": 1, "b": 2}, ttl_seconds=None)  # keys must share a slot if using Cluster
    assert cache.get_many(["a", "b"]) == {"a": 1, "b": 2}
# Or call cache.close() when not using a context manager—the adapter owns the Redis client.
```

### Pydantic models

```python
from pydantic import BaseModel
from async_redis_client import RedisCacheSyncAdapter


class User(BaseModel):
    id: int
    name: str


cache = RedisCacheSyncAdapter.from_standalone_url("redis://localhost:6379/0")

user = User(id=1, name="Ada")
cache.set_model("user:1", user, ttl_seconds=3600)

loaded = cache.get_as_model("user:1", User)
assert loaded == user
```

### Async Redis

```python
import asyncio

from redis.asyncio import Redis
from async_redis_client import RedisCacheAsyncAdapter


async def main():
    client = Redis.from_url("redis://localhost:6379/0", decode_responses=False)
    cache = RedisCacheAsyncAdapter(client)  # owns_client=False: you must await client.aclose()

    await cache.set_json("hello", {"k": "v"})
    got = await cache.get_json("hello")
    await client.aclose()


asyncio.run(main())
```

Or **`RedisCacheAsyncAdapter.from_standalone_url`** / **`from_cluster_url`** with the same `fernet_*` / `key_prefix` options as sync. Those factories own the client—use **`async with RedisCacheAsyncAdapter.from_standalone_url(...) as cache:`** or **`await cache.close()`** when done (`aclose` is the same as `close`).

### In-memory adapter (tests)

```python
from async_redis_client import MemoryCacheSyncAdapter

cache = MemoryCacheSyncAdapter()  # no Fernet/redis; TTL args are ignored on memory adapters
cache.set_json("x", {"n": 1})
assert cache.get_json("x") == {"n": 1}
```

### Errors

- **`CacheError`** — missing key / bootstrap issues (for example unset Fernet key).
- **`DecryptionError`** — invalid Fernet token.
- **`SerializationError`** — wraps Pydantic validation problems after decryption.

Public exports are documented in **`async_redis_client.__init__.__all__`** (ports, adapters, errors, and **`SyncCachePort` / `AsyncCachePort`** aliases).

## Development

```bash
uv sync           # deps + dev (pytest, fakeredis, …)
uv run pytest
```

More design notes and module layout: [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) and [docs/PLAN.md](docs/PLAN.md).

## License

This project is licensed under the [MIT License](LICENSE).

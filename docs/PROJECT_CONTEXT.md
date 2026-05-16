# Project context (working memory)

Use this file when resuming work on **async-redis-client**: goals, stack, design decisions, and what is already in the tree.

## Goal

A **Ports and Adapters (hexagonal)** cache library: **application code depends on cache ports** (`typing.Protocol`); **Redis (or an in-memory stand-in) implements those ports** behind the scenes.

- **Two clients**: synchronous and asynchronous redis-py clients, plus **memory adapters** for tests and simple local use.
- **Topology**: **standalone** and **Redis Cluster** by **injecting** the right redis-py client at startup into `RedisCacheSyncAdapter` / `RedisCacheAsyncAdapter`, or via **`from_standalone_url`** / **`from_cluster_url`**.
- **Connection lifecycle**: build **`Redis`/`RedisCluster`** (and async equivalents) or their pools in the **composition root**; inject into adapters.
- **Cluster hash slots**: multi-key **`set_many`** / **`get_many`** use a pipeline / `MGET`; on Cluster, keys must share a hash slot (hash tags in **`namespace`** / **`key_prefix`** / logical keys, e.g. `{tenant}:item:1`).
- **Key naming**: optional **`namespace`** then **`key_prefix`** are concatenated before the logical key port methods receive — physical Redis key is **`namespace + key_prefix +`** logical key (same composition on memory adapters for parity).
- **Encryption**: in **Redis adapters** — values at encrypted keys are **Fernet** ciphertext; plaintext before encrypt is **UTF-8 JSON bytes** via **Pydantic v2** (`dump_json` / `validate_json` for `JsonValue`, `TypeAdapter` for models). **Optional secondary Fernet key** (`CACHE_FERNET_KEY_SECONDARY` / `fernet_key_secondary`): decrypt retries with the legacy key after primary fails (rotation); **writes always use the primary key only**.
- **JSON helpers**: `set_json` / `get_json` are aliases of `set` / `get`.
- **Typed hydration**: `set_model` / `get_as_model` using **`model_dump_json()`**-derived bytes and **`TypeAdapter(typ).validate_json()`**.
- **TTL** on writes (`SET ... EX ttl` / async equivalent).
- **Atomic counters**: `incr` / `decr` / `incrby` — **plaintext Redis integers** only (no Fernet on counter keys); use a dedicated prefix (e.g. `counter:`).

## Stack (as in `pyproject.toml`)

| Piece | Choice |
|-------|--------|
| Language | Python **≥ 3.11** |
| Package manager | **uv** (`uv.lock` present) |
| Build | **uv_build** |
| Redis client | **redis** (redis-py) **≥ 7.4** (latest stable on PyPI) — optional **`hiredis`** not declared; add if you want the parser speedup |
| Redis server (Docker / e2e) | **Redis 8** (`redis:8-alpine` in `examples/Dockerfile`, root `Dockerfile`, and `test_redis_e2e.py`) |
| Crypto | **cryptography** (Fernet) |
| JSON / models | **pydantic** v2 |

**Dev:** `pytest`, `pytest-asyncio`, `fakeredis`, `pytest-sugar`, **`pytest-cov`**, **`ruff`**, **`taskipy`** (see `[tool.taskipy.tasks]`), **`testcontainers[redis]`** (Docker e2e), **`ty`** (type checks with repo overrides).

## Bootstrap / dev

```bash
cd async-redis-client
uv sync                    # install project + dev deps
uv run pytest              # all tests (includes e2e if Docker is available)
uv run pytest -m "not e2e" # skip Docker-backed Redis e2e locally
```

Common **taskipy** shortcuts: `uv run task lint`, `uv run task test`, `uv run task test-cov`, etc.

The package lives at **`src/async_redis_client/`** (see layout below).

## Ports and adapters

| Layer | Role |
|-------|------|
| **Port** | **`CacheSyncPort`** (`ports/sync_cache_port.py`), **`CacheAsyncPort`** (`ports/async_cache_port.py`) — `typing.Protocol`, **no `redis` imports**; what application code depends on. **`ports/cache_port.py`** re-exports both for backward compatibility. |
| **Redis adapter** | **`RedisCacheSyncAdapter`** (`adapters/redis/sync_adapter.py`), **`RedisCacheAsyncAdapter`** (`adapters/redis/async_adapter.py`) — Fernet + Pydantic; accept `Redis \| RedisCluster` (sync) or `redis.asyncio` equivalents (async). |
| **Memory adapter** | **`MemoryCacheSyncAdapter`**, **`MemoryCacheAsyncAdapter`** — in-process port implementation for unit/domain tests (`TTL` args ignored on memory); **`namespace`** / **`key_prefix`** match Redis physical-key rules. |
| **Composition root** | App bootstrap builds redis clients + adapters, injects **ports** into services. |

Serialization, encryption, and topology stay **inside adapters** (or their classmethods), not in domain code.

## Redis Cluster

- Adapters accept **standalone or cluster** clients as above.
- **Single-key** operations are cluster-safe as usual (MOVED/ASK handled by redis-py).
- **`set_many` / `get_many`**: same hash-slot requirement as any multi-key command on Cluster; adapter does not validate slots — failures surface as Redis errors.

## Testing (current repo)

- **Redis adapters (unit-style):** **`fakeredis`** / **`FakeAsyncRedis`** in `tests/test_redis_sync_adapter.py` and `tests/test_redis_async_adapter.py` (JSON, models, TTL, counters, secondary-key decrypt, wrong key / bad blob, `set_many` / `get_many`, `namespace` / `key_prefix`).
- **Crypto:** `tests/test_crypto.py` (env keys, primary/secondary decrypt behavior).
- **Memory:** `tests/test_memory_async_adapter.py` (async JSON, strict getters, concurrency-oriented cases); sync memory covered via sync/redis-focused tests as applicable.
- **E2E:** `tests/test_redis_e2e.py` — real **Redis 8** in Docker via **`testcontainers[redis]`**, marked **`pytest.mark.e2e`** (skip with `-m "not e2e"` if no daemon).
- **Cluster-specific** integration tests for hash-slot validation remain optional; not a dedicated cluster job in-tree beyond adapter semantics.

## Public API (implemented)

Re-exported from **`async_redis_client`** (see `src/async_redis_client/__init__.py`): ports, errors (**`CacheKeyNotFoundError`** included), **`RedisCacheSyncAdapter`**, **`RedisCacheAsyncAdapter`**, **`MemoryCacheSyncAdapter`**, **`MemoryCacheAsyncAdapter`**, plus aliases **`SyncCachePort`** / **`AsyncCachePort`**.

**Encrypted JSON / model paths**

- `set` / `get` — `JsonValue` round-trip (encrypt/decrypt).
- `set_json` / `get_json` — same as `set` / `get`.
- `get_or_raise_if_missing` / `get_json_or_raise_if_missing` — same decryption path as `get`, but raise **`CacheKeyNotFoundError`** when **no blob is stored** (JSON `null` still counts as present).
- `set_model` / `get_as_model`.
- `delete`, `exists`.
- `set_many` / `get_many` — batch pipeline + `MGET` semantics; Cluster hash-slot rules apply.

**Counters** (plaintext)

- `incr`, `decr`, `incrby`.

**Factories (Redis only)**

- `from_standalone_url`, `from_cluster_url` (sync and async), with **`fernet_key`** / **`fernet_key_secondary`** / **`namespace`** / **`key_prefix`** mirroring the constructors.

## Configuration

- **Fernet key**: env **`CACHE_FERNET_KEY`** (urlsafe base64 ASCII) and/or constructor **`fernet_key: bytes`** — explicit key wins (`crypto.build_fernet`).
- **Secondary Fernet key (rotation)**: env **`CACHE_FERNET_KEY_SECONDARY`** and/or **`fernet_key_secondary: bytes`** — used only for decrypt fallback (`crypto.build_secondary_fernet` / `decrypt_bytes`).
- **`namespace`**: optional string placed **before** **`key_prefix`** in the physical key (Redis and memory adapters).
- **`key_prefix`**: optional string between **`namespace`** and the logical key (Redis and memory adapters).

## Errors

- **`CacheError`** base — configuration problems such as a missing Fernet key when building an adapter.
- **`CacheKeyNotFoundError`** — strict JSON reads via **`get_or_raise_if_missing`** / **`get_json_or_raise_if_missing`** when the key has **no stored JSON ciphertext** (Redis **`GET`** miss or memory JSON slot absent).
- **`DecryptionError`** — bad/truncated Fernet token (decrypt attempted because Redis returned a value).
- **`SerializationError`** — wraps Pydantic **`ValidationError`** (and related value errors) after decrypt for a stable public surface.
- **Key not found (optional)**: plain **`get`** / **`get_json`** / **`get_as_model`** return **`None`**; **`get_many`** maps each missing logical key to **`None`**. Use **`get_or_raise_if_missing`** when callers prefer an exception over **`None`**. Invalid ciphertext / JSON after a hit still raises **`DecryptionError`** / **`SerializationError`**.

## Module layout (current)

Under **`src/async_redis_client/`**:

| Path | Role |
|------|------|
| `__init__.py` | Public exports |
| `ports/sync_cache_port.py` | **`CacheSyncPort`** |
| `ports/async_cache_port.py` | **`CacheAsyncPort`** |
| `ports/cache_port.py` | Re-exports sync + async ports (compat) |
| `errors.py` | **`CacheError`**, **`CacheKeyNotFoundError`**, **`DecryptionError`**, **`SerializationError`** |
| `crypto.py` | Env + **`build_fernet`**, **`build_secondary_fernet`**, **`encrypt_bytes`**, **`decrypt_bytes`** (primary + optional secondary) |
| `serialization.py` | **`dump_json_value`**, **`load_json_value`**, **`dump_model`**, **`load_as_type`** |
| `adapters/redis/sync_adapter.py` | **`RedisCacheSyncAdapter`** |
| `adapters/redis/async_adapter.py` | **`RedisCacheAsyncAdapter`** |
| `adapters/memory/sync_adapter.py` | **`MemoryCacheSyncAdapter`** |
| `adapters/memory/async_adapter.py` | **`MemoryCacheAsyncAdapter`** |

## Out of scope (v1)

- KMS / centralized key lifecycle beyond **constructor/env dual-key decrypt** (`fernet_key_secondary`), compression before encrypt.
- **Redis Sentinel** as a first-class factory (same inject-a-client pattern can be added later).

## Related docs

- Broader plan / rationale: [PLAN.md](PLAN.md).
- Usage and config examples: root [README.md](../README.md).

## Follow-ups (optional)

- [ ] Optional **`hiredis`** dependency if benchmarks justify it.
- [ ] Docker / CI job explicitly exercising **Redis Cluster** + `set_many` / `get_many` hash-slot behavior (beyond standalone e2e).

---

*Last aligned with the repo: **async-redis-client** v0.1.0 — hexagonal ports (`sync`/`async` modules + compat `cache_port`), Redis + memory adapters, optional **`namespace`** + **`key_prefix`** physical keys, Fernet primary/secondary decrypt, Pydantic JSON, plaintext counters, batch helpers, fakeredis + crypto tests, optional Docker e2e via testcontainers.*

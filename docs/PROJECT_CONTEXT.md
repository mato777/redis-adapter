# Project context (working memory)

Use this file when resuming work on **async-redis-client**: goals, stack, design decisions, and what is already in the tree.

## Goal

A **Ports and Adapters (hexagonal)** library for **cache** and **pub/sub**: application code depends on **`typing.Protocol`** ports; **Redis** (sync or asyncio) or **in-memory** adapters implement them in the composition root.

### Cache

- **Two clients**: synchronous and asynchronous redis-py clients, plus **memory adapters** for tests and simple local use.
- **Topology**: **standalone** and **Redis Cluster** by **injecting** the right redis-py client at startup into `RedisCacheSyncAdapter` / `RedisCacheAsyncAdapter`, or via **`from_standalone_url`** / **`from_cluster_url`**.
- **Connection lifecycle**: build **`Redis`/`RedisCluster`** (and async equivalents) or their pools in the **composition root**; inject into adapters.
- **Cluster hash slots**: multi-key **`set_many`** / **`get_many`** use a pipeline / `MGET`; on Cluster, keys must share a hash slot (hash tags in **`namespace`** / **`key_prefix`** / logical keys, e.g. `{tenant}:item:1`).
- **Key naming**: optional **`namespace`** then **`key_prefix`** are concatenated before the logical key port methods receive — physical Redis key is **`namespace + key_prefix +`** logical key (same composition on memory adapters for parity).
- **Encryption**: in **Redis cache adapters** — values at encrypted keys are **Fernet** ciphertext; plaintext before encrypt is **UTF-8 JSON bytes** via **Pydantic v2** (`dump_json` / `validate_json` for `JsonValue`, `TypeAdapter` for models). **Optional secondary Fernet key** (`CACHE_FERNET_KEY_SECONDARY` / `fernet_key_secondary`): decrypt retries with the legacy key after primary fails (rotation); **writes always use the primary key only**.
- **JSON helpers**: `set_json` / `get_json` are aliases of `set` / `get`.
- **Typed hydration**: `set_model` / `get_as_model` using **`model_dump_json()`**-derived bytes and **`TypeAdapter(typ).validate_json()`**.
- **TTL** on writes (`SET ... EX ttl` / async equivalent).
- **Atomic counters**: `incr` / `decr` / `incrby` — **plaintext Redis integers** only (no Fernet on counter keys); use a dedicated prefix (e.g. `counter:`).

### Pub/sub (v0.2+)

Low-level **ports** mirror Redis pub/sub:

- **`PubSubSyncPort`** / **`PubSubAsyncPort`** — `publish`, `subscribe`, `psubscribe`, `close`.
- **`PubSubSubscription*Port`** — `get_message`, `listen`, `unsubscribe`, `close`.
- Optional **`channel_prefix`** on Redis/memory adapters (same idea as cache `key_prefix`).
- Wire payloads: **`PubSubMessage`** (`schemas/pubsub_message.py`) — `channel`, `data`, optional `pattern` for `pmessage`.

**Typed messaging** (application-facing, built on pub/sub ports):

- **`PubSubProducerSync`** / **`PubSubProducerAsync`** — encode **Pydantic `BaseModel`** or **dataclass** as JSON and publish.
- **`PubSubConsumerSync`** / **`PubSubConsumerAsync`** — subscribe, decode, call a user **handler**; extra deps (`db`, cache, …) passed as constructor kwargs and matched to handler parameter **names** (validated at consumer construction).
- One class per file under **`messaging/`** (`producer_sync.py`, `producer_async.py`, `consumer_sync.py`, `consumer_async.py`); shared **`codec.py`** and **`_invoke.py`**.

Example: **`examples/pubsub_example.py`**.

## Stack (as in `pyproject.toml`)

| Piece | Choice |
|-------|--------|
| Language | Python **≥ 3.11** |
| Package manager | **uv** (`uv.lock` present) |
| Build | **uv_build** |
| Version | **0.2.0** |
| Redis client | **redis** (redis-py) **≥ 7.4** (latest stable on PyPI) — optional **`hiredis`** not declared; add if you want the parser speedup |
| Redis server (Docker / e2e) | **Redis 8** (`redis:8-alpine` in root `Dockerfile`, `test_redis_e2e.py`, `test_pubsub_e2e.py`) |
| Crypto | **cryptography** (Fernet) |
| JSON / models | **pydantic** v2 |

**Dev:** `pytest`, `pytest-asyncio`, `fakeredis`, `pytest-sugar`, **`pytest-cov`**, **`ruff`**, **`taskipy`** (see `[tool.taskipy.tasks]`), **`testcontainers[redis]`** (Docker e2e), **`ty`** (type checks with repo overrides on `adapters/redis/**` and `tests/**`).

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
| **Cache port** | **`CacheSyncPort`**, **`CacheAsyncPort`** — `ports/sync_cache_port.py`, `ports/async_cache_port.py`; **`ports/cache_port.py`** re-exports (compat). |
| **Pub/sub port** | **`PubSubSyncPort`**, **`PubSubAsyncPort`**, subscription ports — `ports/sync_pubsub_port.py`, `ports/async_pubsub_port.py`; **`ports/pubsub_port.py`** re-exports (compat). |
| **Redis adapter** | Cache: **`RedisCacheSyncAdapter`**, **`RedisCacheAsyncAdapter`**. Pub/sub: **`RedisPubSubSyncAdapter`**, **`RedisPubSubAsyncAdapter`**. |
| **Memory adapter** | Cache: **`MemoryCacheSyncAdapter`**, **`MemoryCacheAsyncAdapter`**. Pub/sub: **`MemoryPubSubSyncAdapter`**, **`MemoryPubSubAsyncAdapter`**. |
| **Messaging** | Not ports — **`PubSubProducer*`**, **`PubSubConsumer*`** depend on pub/sub ports only. |
| **Composition root** | Bootstrap builds redis clients + adapters; inject **ports** (or messaging wrappers) into services. |

Serialization, encryption, and topology stay **inside adapters** (or messaging codec), not in domain code.

## Redis Cluster

- Adapters accept **standalone or cluster** clients as above.
- **Single-key** operations are cluster-safe as usual (MOVED/ASK handled by redis-py).
- **`set_many` / `get_many`**: same hash-slot requirement as any multi-key command on Cluster; adapter does not validate slots — failures surface as Redis errors.
- **Pub/sub on Cluster** has Redis-specific fan-out semantics; library does not abstract slot routing for channels.

## Testing (current repo)

- **Cache (Redis, unit-style):** `tests/test_redis_sync_adapter.py`, `tests/test_redis_async_adapter.py` — **fakeredis** / **FakeAsyncRedis** (JSON, models, TTL, counters, secondary-key decrypt, batch, `namespace` / `key_prefix`).
- **Cache (memory):** `tests/test_memory_async_adapter.py` and sync coverage via redis/memory tests.
- **Pub/sub (Redis, unit-style):** `tests/test_redis_pubsub_sync_adapter.py`, `tests/test_redis_pubsub_async_adapter.py` — fakeredis.
- **Pub/sub (memory):** `tests/test_memory_pubsub_adapter.py`.
- **Pub/sub (helpers):** `tests/test_pubsub_helpers.py`.
- **Messaging:** `tests/test_messaging_codec.py`, `tests/test_messaging_producer_consumer.py` — codec + producer/consumer with memory bus and dependency injection.
- **Crypto:** `tests/test_crypto.py`.
- **E2E cache:** `tests/test_redis_e2e.py` — **Redis 8** via **testcontainers**, `pytest.mark.e2e`.
- **E2E pub/sub:** `tests/test_pubsub_e2e.py` — same container fixture, sync + async roundtrip.
- **Cluster-specific** hash-slot integration tests remain optional.

## Public API (implemented)

Re-exported from **`async_redis_client`** (see `src/async_redis_client/__init__.py`).

**Ports (aliases):** `SyncCachePort`, `AsyncCachePort`, `SyncPubSubPort`, `AsyncPubSubPort`, plus `CacheSyncPort`, `CacheAsyncPort`, `PubSubSyncPort`, `PubSubAsyncPort`, subscription port types.

**Cache adapters:** `RedisCacheSyncAdapter`, `RedisCacheAsyncAdapter`, `MemoryCacheSyncAdapter`, `MemoryCacheAsyncAdapter`.

**Pub/sub adapters:** `RedisPubSubSyncAdapter`, `RedisPubSubAsyncAdapter`, `MemoryPubSubSyncAdapter`, `MemoryPubSubAsyncAdapter`.

**Messaging:** `PubSubProducerSync`, `PubSubProducerAsync`, `PubSubConsumerSync`, `PubSubConsumerAsync`.

**Schemas:** `PubSubMessage`.

**Errors:** `CacheError`, `CacheClosedError`, `CacheKeyNotFoundError`, `DecryptionError`, `SerializationError`, `PubSubError`, `PubSubClosedError`.

### Cache API summary

- Encrypted JSON: `set` / `get`, `set_json` / `get_json`, strict getters, `set_model` / `get_as_model`, `delete`, `exists`, `set_many` / `get_many`.
- Counters (plaintext): `incr`, `decr`, `incrby`.
- Factories: `from_standalone_url`, `from_cluster_url` with `fernet_*`, `namespace`, `key_prefix`.

### Pub/sub API summary

- Low-level: `publish(channel, bytes|str)`, `subscribe` / `psubscribe` → subscription with `get_message` / `listen`.
- Messaging: `producer.publish(typed_message)`, `consumer.run(max_messages=…, stop_event=…)` (async).

## Configuration

- **Fernet key**: env **`CACHE_FERNET_KEY`** and/or constructor **`fernet_key: bytes`** — explicit key wins (`crypto.build_fernet`).
- **Secondary Fernet key (rotation)**: env **`CACHE_FERNET_KEY_SECONDARY`** and/or **`fernet_key_secondary: bytes`** — decrypt fallback only.
- **`namespace`** / **`key_prefix`**: cache physical keys (Redis + memory).
- **`channel_prefix`**: pub/sub physical channel names (Redis + memory).

## Errors

- **`CacheError`** / **`PubSubError`** — base types for each area.
- **`CacheClosedError`** / **`PubSubClosedError`** — use after adapter (or subscription) close.
- **`CacheKeyNotFoundError`** — strict cache JSON reads when key absent.
- **`DecryptionError`** — invalid Fernet token on cache read.
- **`SerializationError`** — Pydantic validation failure (cache decrypt path or pub/sub message decode).
- Optional cache misses: plain `get*` returns **`None`**; invalid ciphertext/JSON after hit raises **`DecryptionError`** / **`SerializationError`**.

## Module layout (current)

Under **`src/async_redis_client/`**:

| Path | Role |
|------|------|
| `__init__.py` | Public exports |
| `errors.py` | Cache + pub/sub exceptions |
| `crypto.py` | Fernet build/encrypt/decrypt |
| `serialization.py` | Cache JSON/model bytes |
| `schemas/pubsub_message.py` | **`PubSubMessage`** dataclass |
| `schemas/__init__.py` | Re-export **`PubSubMessage`** |
| `ports/sync_cache_port.py` | **`CacheSyncPort`** |
| `ports/async_cache_port.py` | **`CacheAsyncPort`** |
| `ports/sync_pubsub_port.py` | **`PubSubSyncPort`**, **`PubSubSubscriptionSyncPort`** |
| `ports/async_pubsub_port.py` | **`PubSubAsyncPort`**, **`PubSubSubscriptionAsyncPort`** |
| `ports/cache_port.py` / `ports/pubsub_port.py` | Compat re-exports |
| `adapters/redis/sync_adapter.py` | **`RedisCacheSyncAdapter`** |
| `adapters/redis/async_adapter.py` | **`RedisCacheAsyncAdapter`** |
| `adapters/redis/pubsub_sync_adapter.py` | **`RedisPubSubSyncAdapter`** (+ subscription class) |
| `adapters/redis/pubsub_async_adapter.py` | **`RedisPubSubAsyncAdapter`** (+ subscription class) |
| `adapters/redis/_helpers.py` | Cache key/pipeline helpers |
| `adapters/redis/_pubsub_helpers.py` | Channel prefix, parse Redis pub/sub dicts |
| `adapters/memory/sync_adapter.py` | **`MemoryCacheSyncAdapter`** |
| `adapters/memory/async_adapter.py` | **`MemoryCacheAsyncAdapter`** |
| `adapters/memory/pubsub_sync_adapter.py` | **`MemoryPubSubSyncAdapter`** |
| `adapters/memory/pubsub_async_adapter.py` | **`MemoryPubSubAsyncAdapter`** |
| `adapters/memory/_pubsub_hub.py` | In-process fan-out for memory pub/sub |
| `messaging/codec.py` | Encode/decode typed messages (JSON) |
| `messaging/_invoke.py` | Handler binding + dependency validation |
| `messaging/producer_sync.py` | **`PubSubProducerSync`** |
| `messaging/producer_async.py` | **`PubSubProducerAsync`** |
| `messaging/consumer_sync.py` | **`PubSubConsumerSync`** |
| `messaging/consumer_async.py` | **`PubSubConsumerAsync`** |
| `messaging/__init__.py` | Re-export all four messaging classes |

**Examples:** `examples/sync_redis_example.py`, `examples/async_redis_example.py`, `examples/memory_cache_example.py`, `examples/pubsub_example.py`.

## Out of scope

- KMS / centralized key lifecycle beyond **constructor/env dual-key decrypt** (`fernet_key_secondary`), compression before encrypt.
- **Redis Sentinel** as a first-class factory (same inject-a-client pattern can be added later).
- **FastAPI / web framework** integration in the library (use messaging + ports in app bootstrap).
- Durable queues, consumer groups, or **Redis Streams** (use pub/sub for fire-and-forget notifications only).

## Related docs

- Broader plan / rationale: [PLAN.md](PLAN.md).
- Usage and config examples: root [README.md](../README.md).

## Follow-ups (optional)

- [ ] Optional **`hiredis`** dependency if benchmarks justify it.
- [ ] Docker / CI job explicitly exercising **Redis Cluster** + `set_many` / `get_many` hash-slot behavior (beyond standalone e2e).
- [ ] E2E test for **typed messaging** (`PubSubProducerAsync` + `PubSubConsumerAsync`) against real Redis (today covered via memory + fakeredis + low-level pub/sub e2e).

---

*Last aligned with the repo: **async-redis-client** v0.2.0 — cache + pub/sub ports, Redis + memory adapters, `schemas/`, typed **messaging** (four producer/consumer modules), Fernet cache encryption, Pydantic JSON, fakeredis + messaging tests, Docker e2e for cache and pub/sub via testcontainers.*

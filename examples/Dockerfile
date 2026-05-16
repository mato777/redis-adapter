# Minimal Redis server for running the scripts in this folder.
#
# Build and run from the repository root (or any directory):
#
#   docker build -f examples/Dockerfile -t async-redis-client-examples-redis examples/
#   docker run --rm -p 6379:6379 async-redis-client-examples-redis
#
# Then install the library locally (`uv sync`) and run an example with:
#
#   REDIS_URL=redis://127.0.0.1:6379/0 uv run python examples/sync_redis_example.py
#
# Pin major version to stay aligned with redis-py expectations (see tests/test_redis_e2e.py).
FROM redis:8-alpine
EXPOSE 6379

"""Smoke tests that the installable package exposes the public API."""

import importlib.metadata

import async_redis_client


def test_package_version() -> None:
    assert async_redis_client.__version__
    assert (
        importlib.metadata.version("async-redis-client")
        == async_redis_client.__version__
    )


def test_public_exports_are_importable() -> None:
    for name in async_redis_client.__all__:
        assert getattr(async_redis_client, name) is not None

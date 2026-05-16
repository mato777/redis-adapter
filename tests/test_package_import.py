"""Smoke tests that the installable package exposes the public API."""

import importlib.metadata
from importlib.metadata import PackageNotFoundError

import pytest

import async_redis_client
import async_redis_client as pkg_init


def test_package_version() -> None:
    assert async_redis_client.__version__
    assert (
        importlib.metadata.version("async-redis-client")
        == async_redis_client.__version__
    )


def test_package_version_when_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    def raise_not_found(_name: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", raise_not_found)
    reloaded = importlib.reload(pkg_init)
    try:
        assert reloaded.__version__ == "0.0.0+unknown"
    finally:
        importlib.reload(pkg_init)


def test_pubsub_port_backward_compat_reexports() -> None:
    from async_redis_client.ports import pubsub_port

    assert pubsub_port.PubSubAsyncPort is async_redis_client.PubSubAsyncPort
    assert pubsub_port.PubSubSyncPort is async_redis_client.PubSubSyncPort
    assert set(pubsub_port.__all__) == {
        "PubSubAsyncPort",
        "PubSubSubscriptionAsyncPort",
        "PubSubSubscriptionSyncPort",
        "PubSubSyncPort",
    }


def test_public_exports_are_importable() -> None:
    for name in async_redis_client.__all__:
        assert getattr(async_redis_client, name) is not None

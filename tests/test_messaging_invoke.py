from __future__ import annotations

import inspect

import pytest

from async_redis_client.messaging._invoke import (
    invoke_handler_async,
    invoke_handler_sync,
    validate_handler_dependencies,
)


def test_validate_rejects_no_parameters() -> None:
    with pytest.raises(TypeError, match="at least one parameter"):
        validate_handler_dependencies(lambda: None, {})


def test_validate_rejects_self_first_parameter() -> None:
    def handler(self, msg: str) -> None:
        pass

    with pytest.raises(TypeError, match="not a method"):
        validate_handler_dependencies(handler, {})


def test_validate_allows_parameter_with_default() -> None:
    def handler(msg: str, tag: str = "x") -> None:
        pass

    validate_handler_dependencies(handler, {})


def test_validate_reports_missing_dependencies() -> None:
    def handler(msg: str, db: object) -> None:
        pass

    with pytest.raises(TypeError, match="missing required parameters"):
        validate_handler_dependencies(handler, {})


@pytest.mark.asyncio
async def test_invoke_async_runs_sync_and_async_handlers() -> None:
    seen: list[str] = []

    def sync_handler(msg: str) -> None:
        seen.append(f"sync:{msg}")

    async def async_handler(msg: str) -> None:
        seen.append(f"async:{msg}")

    await invoke_handler_async(sync_handler, "a", {})
    await invoke_handler_async(async_handler, "b", {})
    assert seen == ["sync:a", "async:b"]


def test_invoke_sync_rejects_async_handler() -> None:
    async def async_handler(msg: str) -> None:
        pass

    with pytest.raises(TypeError, match="async handlers"):
        invoke_handler_sync(async_handler, "x", {})


def test_bind_handler_kwargs_includes_dependencies() -> None:
    def handler(msg: str, db: object, *, tag: str = "t") -> str:
        return f"{msg}:{tag}"

    invoke_handler_sync(handler, "hi", {"db": object(), "tag": "ok"})


def test_missing_dependency_at_invoke_time() -> None:
    def handler(msg: str, db: object) -> None:
        pass

    with pytest.raises(TypeError, match="missing required parameters"):
        invoke_handler_sync(handler, "m", {})


def test_optional_positional_kind_not_required() -> None:
    def handler(msg: str, opt: str = "default") -> None:
        pass

    sig = inspect.signature(handler)
    from async_redis_client.messaging._invoke import _missing_dependency_names

    assert _missing_dependency_names(sig, "msg", {}) == []

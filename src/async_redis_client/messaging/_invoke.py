from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any


def _message_parameter_name(handler: Callable[..., Any]) -> str:
    sig = inspect.signature(handler)
    if not sig.parameters:
        raise TypeError("handler must accept at least one parameter (the message)")
    return next(iter(sig.parameters))


def _missing_dependency_names(
    handler: Callable[..., Any],
    dependencies: dict[str, Any],
) -> list[str]:
    message_name = _message_parameter_name(handler)
    missing: list[str] = []
    for name, param in inspect.signature(handler).parameters.items():
        if name == message_name:
            continue
        if name in dependencies:
            continue
        if param.default is not inspect.Parameter.empty:
            continue
        if param.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            missing.append(name)
    return missing


def validate_handler_dependencies(
    handler: Callable[..., Any],
    dependencies: dict[str, Any],
) -> None:
    missing = _missing_dependency_names(handler, dependencies)
    if missing:
        raise TypeError(
            f"handler is missing required parameters {missing!r}; "
            "pass them via consumer dependencies"
        )


def _bind_handler_kwargs(
    handler: Callable[..., Any],
    message: object,
    dependencies: dict[str, Any],
) -> dict[str, Any]:
    message_name = _message_parameter_name(handler)
    bound: dict[str, Any] = {message_name: message}

    for name, value in dependencies.items():
        if name in inspect.signature(handler).parameters and name != message_name:
            bound[name] = value

    missing = _missing_dependency_names(handler, dependencies)
    if missing:
        raise TypeError(
            f"handler is missing required parameters {missing!r}; "
            "pass them via consumer dependencies"
        )
    return bound


async def invoke_handler_async(
    handler: Callable[..., Any],
    message: object,
    dependencies: dict[str, Any],
) -> None:
    bound = _bind_handler_kwargs(handler, message, dependencies)
    result = handler(**bound)
    if inspect.isawaitable(result):
        await result


def invoke_handler_sync(
    handler: Callable[..., Any],
    message: object,
    dependencies: dict[str, Any],
) -> None:
    bound = _bind_handler_kwargs(handler, message, dependencies)
    result = handler(**bound)
    if inspect.isawaitable(result):
        raise TypeError(
            "sync consumer does not support async handlers; use PubSubConsumerAsync"
        )

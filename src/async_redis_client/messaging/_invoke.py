from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any


def _reject_bound_method(handler: Callable[..., Any]) -> None:
    if inspect.ismethod(handler):
        raise TypeError(
            "handler must be a plain function or functools.partial, not a bound method; "
            "pass dependencies via consumer kwargs instead"
        )


def _handler_signature(handler: Callable[..., Any]) -> inspect.Signature:
    return inspect.signature(handler)


def _message_parameter_name(sig: inspect.Signature) -> str:
    if not sig.parameters:
        raise TypeError("handler must accept at least one parameter (the message)")
    name = next(iter(sig.parameters))
    if name in ("self", "cls"):
        raise TypeError(
            "handler must be a plain function or functools.partial, not a method; "
            "pass dependencies via consumer kwargs instead"
        )
    return name


def _missing_dependency_names(
    sig: inspect.Signature,
    message_name: str,
    dependencies: dict[str, Any],
) -> list[str]:
    missing: list[str] = []
    for name, param in sig.parameters.items():
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
    _reject_bound_method(handler)
    sig = _handler_signature(handler)
    message_name = _message_parameter_name(sig)
    missing = _missing_dependency_names(sig, message_name, dependencies)
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
    _reject_bound_method(handler)
    sig = _handler_signature(handler)
    message_name = _message_parameter_name(sig)
    bound: dict[str, Any] = {message_name: message}

    for name, value in dependencies.items():
        if name in sig.parameters and name != message_name:
            bound[name] = value

    missing = _missing_dependency_names(sig, message_name, dependencies)
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

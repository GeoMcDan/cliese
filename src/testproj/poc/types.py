from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

# Core invocation types


@dataclass
class Invocation:
    """Invocation context passed through the middleware pipeline.

    - app: the Typer app (or ExtendedTyper) executing the command
    - original: the original user function
    - target: the decorated function whose signature Typer inspects
    - args/kwargs: parsed args from Typer
    - state: scratch space shared across middlewares
    - name: command name (optional)
    """

    app: Any
    original: Callable[..., Any]
    target: Callable[..., Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    name: str | None = None
    state: dict[str, Any] = field(default_factory=dict)


class CommandHandler(Protocol):
    def __call__(self, inv: Invocation) -> Any:  # pragma: no cover - protocol
        ...


class Middleware(Protocol):
    """Middleware shape: takes next handler, returns a new handler."""

    def __call__(self, next: CommandHandler) -> CommandHandler:  # pragma: no cover
        ...


# Decorator type used to transform function signature/metadata
Decorator = Callable[[Callable[..., Any]], Callable[..., Any]]


class InvocationFactory(Protocol):
    """Factory responsible for creating the Invocation passed through the pipeline."""

    def __call__(
        self,
        *,
        app: Any,
        original: Callable[..., Any],
        target: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        name: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> Invocation:  # pragma: no cover - protocol
        ...


def ensure_signature(func: Callable[..., Any]) -> Callable[..., Any]:
    """Ensure the callable exposes a concrete inspect.Signature.

    If the callable lacks a __signature__, one is derived via inspect.signature.
    This helps Typer read the correct signature when wrappers are involved.
    """

    if getattr(func, "__signature__", None) is None:
        try:
            sig = inspect.signature(func)
        except (TypeError, ValueError):  # builtins or callables without signature
            return func
        func.__signature__ = sig
    return func

from __future__ import annotations

import inspect
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Protocol

# Core invocation types


@dataclass
class InvocationEnvironment:
    """Runtime context describing the invocation environment.

    - app: the Typer (or Typer-like) application instance
    - name: command name, when known
    - context: optional execution context (Typer/Click or custom)
    """

    app: Any
    name: str | None = None
    context: Any | None = None

    def with_context(self, context: Any | None) -> "InvocationEnvironment":
        """Return a copy updated with a different context object."""

        return replace(self, context=context)


@dataclass
class InvocationCall:
    """Arguments Typer resolved for the current invocation."""

    args: tuple[Any, ...]
    kwargs: dict[str, Any]

    def clone(
        self,
        *,
        args: tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> "InvocationCall":
        """Return a copy with updated positional/keyword arguments."""

        new_args = args if args is not None else self.args
        new_kwargs = kwargs.copy() if kwargs is not None else self.kwargs.copy()
        return InvocationCall(args=new_args, kwargs=new_kwargs)


@dataclass
class Invocation:
    """Invocation context passed through the middleware pipeline.

    - original: the original user function supplied by the developer
    - target: the decorated function whose signature Typer inspects
    - environment: contextual metadata about the invocation
    - call: positional/keyword arguments Typer resolved
    - state: scratch space shared across middlewares
    """

    original: Callable[..., Any]
    target: Callable[..., Any]
    environment: InvocationEnvironment
    call: InvocationCall
    state: dict[str, Any] = field(default_factory=dict)

    @property
    def app(self) -> Any:
        return self.environment.app

    @property
    def name(self) -> str | None:
        return self.environment.name

    @property
    def context(self) -> Any | None:
        return self.environment.context

    @property
    def args(self) -> tuple[Any, ...]:
        return self.call.args

    @property
    def kwargs(self) -> dict[str, Any]:
        return self.call.kwargs


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
        original: Callable[..., Any],
        target: Callable[..., Any],
        environment: InvocationEnvironment,
        call: InvocationCall,
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

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
    _context: "InvocationContext | None" = field(default=None, init=False, repr=False)

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

    @property
    def command_context(self) -> "InvocationContext":
        """Return the reusable command context exposed to handlers."""

        if self._context is None:
            self._context = InvocationContext(invocation=self)
        return self._context

    # Backward compatible alias
    ctx = command_context

    def resolve_call_arguments(self) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Return (args, kwargs) including any framework-managed injections."""

        original_sig = getattr(self.target, "__typerplus_original_signature__", None)
        context_param_names: tuple[str, ...] = getattr(
            self.target, "__typerplus_context_param_names__", ()
        )
        virtual_param_names: tuple[str, ...] = getattr(
            self.target, "__typerplus_virtual_param_names__", ()
        )

        exec_sig = original_sig or inspect.signature(self.target)
        context_names_set = set(context_param_names)
        virtual_names_set = set(virtual_param_names)

        args_list = list(self.call.args)
        kwargs_map = dict(self.call.kwargs)
        # Remove virtual parameters from the working kwargs map so they are not forwarded.
        for virtual_name in virtual_names_set:
            kwargs_map.pop(virtual_name, None)

        final_args: list[Any] = []
        final_kwargs: dict[str, Any] = {}
        idx = 0
        context_value = self.command_context

        for name, param in exec_sig.parameters.items():
            if name in context_names_set:
                if param.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                ):
                    final_args.append(context_value)
                else:
                    final_kwargs[name] = context_value
                continue

            if name in virtual_names_set:
                if param.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                ) and idx < len(args_list):
                    idx += 1
                continue

            if param.kind is inspect.Parameter.VAR_POSITIONAL:
                if idx < len(args_list):
                    final_args.extend(args_list[idx:])
                    idx = len(args_list)
                continue

            if param.kind is inspect.Parameter.VAR_KEYWORD:
                if kwargs_map:
                    final_kwargs.update(kwargs_map)
                    kwargs_map = {}
                continue

            if param.kind is inspect.Parameter.KEYWORD_ONLY:
                if name in kwargs_map:
                    final_kwargs[name] = kwargs_map.pop(name)
                continue

            if param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                if name in kwargs_map:
                    final_kwargs[name] = kwargs_map.pop(name)
                    continue
                if idx < len(args_list):
                    final_args.append(args_list[idx])
                    idx += 1
                continue

        if kwargs_map:
            final_kwargs.update(kwargs_map)

        return tuple(final_args), final_kwargs

    def invoke_target(self) -> Any:
        """Invoke the target callable using the resolved argument set."""

        args, kwargs = self.resolve_call_arguments()
        return self.target(*args, **kwargs)


@dataclass(slots=True)
class InvocationContext:
    """User-facing command context exposing invocation metadata/state."""

    invocation: Invocation

    @property
    def app(self) -> Any:
        return self.invocation.app

    @property
    def name(self) -> str | None:
        return self.invocation.name

    @property
    def click_context(self) -> Any | None:
        return self.invocation.context

    @property
    def state(self) -> dict[str, Any]:
        return self.invocation.state

    @property
    def args(self) -> tuple[Any, ...]:
        return self.invocation.args

    @property
    def kwargs(self) -> dict[str, Any]:
        return self.invocation.kwargs

    def get_state(self, key: str, default: Any | None = None) -> Any | None:
        """Convenience accessor mirroring dict.get against shared state."""

        return self.state.get(key, default)


# Friendly alias matching Click/Typer naming conventions
CommandContext = InvocationContext


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

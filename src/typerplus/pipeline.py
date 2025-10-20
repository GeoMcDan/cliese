from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Iterable, Sequence

import click
import typer
from typer.models import ParameterInfo

from .annotation import TyperAnnotation
from .types import (
    CommandContext,
    CommandHandler,
    Decorator,
    Invocation,
    InvocationCall,
    InvocationContext,
    InvocationEnvironment,
    InvocationFactory,
    Middleware,
    ensure_signature,
)


def _instantiate_parser(factory: Callable[[], Any] | type | Any | None) -> Any:
    if factory is None:
        return None
    if isinstance(factory, type):
        return factory()
    if callable(factory):
        return factory()
    return factory


def _create_param_type_hook(
    param_type: type,
    option_factory: Callable[[inspect.Parameter], ParameterInfo] | None,
    parser_factory: Callable[[], Any] | type | Any | None,
) -> Decorator:
    """Return a decorator that amends matching parameters with Option metadata."""

    def ensure(func: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(func)
        params = []
        touched = False

        for param in sig.parameters.values():
            annot = TyperAnnotation(param.annotation)
            target_type = annot.type

            match = False
            if target_type is param_type:
                match = True
            elif isinstance(target_type, type) and isinstance(param_type, type):
                match = issubclass(target_type, param_type)

            if not match:
                params.append(param)
                continue

            option = next(annot.find_parameter_info_arg(), None)
            metadata = list(annot.metadata_without_parameter_info())

            if option is None:
                if option_factory is None:
                    raise ValueError(
                        f"Parameter '{param.name}' is missing option metadata for {param_type!r}"
                    )
                option = option_factory(param)

            metadata.append(option)

            if (
                getattr(option, "click_type", None) is None
                and parser_factory is not None
            ):
                option.click_type = _instantiate_parser(parser_factory)

            new_annotation = annot.rebuild(annotations=metadata)
            default = param.default
            if default is inspect.Signature.empty:
                default = None

            params.append(param.replace(annotation=new_annotation, default=default))
            touched = True

        if not touched:
            return func

        func.__signature__ = sig.replace(parameters=params)
        return func

    return ensure


@dataclass(frozen=True)
class _VirtualParameter:
    name: str
    parameter: inspect.Parameter
    state_key: str | None
    default_value: Any


def _default_virtual_option(name: str, *, default: Any = False) -> ParameterInfo:
    flag = f"--{name.replace('_', '-')}"
    kwargs: dict[str, Any] = {
        "help": f"Enable {name.replace('_', ' ')}.",
        "show_default": True,
    }
    return typer.Option(default, flag, **kwargs)


def _create_virtual_option_parameter(
    name: str,
    *,
    option: ParameterInfo,
    annotation_type: Any,
) -> inspect.Parameter:
    return inspect.Parameter(
        name,
        kind=inspect.Parameter.KEYWORD_ONLY,
        annotation=annotation_type,
        default=option,
    )


def _apply_virtual_parameters(
    func: Callable[..., Any],
    params: Sequence[_VirtualParameter],
) -> Callable[..., Any]:
    if not params:
        return func

    sig = inspect.signature(func)
    existing_params = list(sig.parameters.values())
    existing_names = {param.name for param in existing_params}

    added: list[str] = []
    for virtual in params:
        if virtual.name in existing_names:
            continue
        existing_params.append(virtual.parameter)
        added.append(virtual.name)

    if not added:
        return func

    func.__signature__ = sig.replace(parameters=existing_params)
    current = getattr(func, "__typerplus_virtual_param_names__", ())
    func.__typerplus_virtual_param_names__ = tuple(current) + tuple(added)
    return func


_CONTEXT_TYPE_SENTINELS = {"InvocationContext", "CommandContext"}


def _is_invocation_context_annotation(annotation: Any) -> bool:
    annot = TyperAnnotation(annotation)
    target = annot.type

    if target in (InvocationContext, CommandContext):
        return True

    if isinstance(target, str) and target in _CONTEXT_TYPE_SENTINELS:
        return True

    return False


def _ensure_invocation_context_parameter(
    func: Callable[..., Any],
) -> Callable[..., Any]:
    """Hide InvocationContext parameters from Typer while tracking them for injection."""

    if getattr(func, "__typerplus_context_param_names__", None):
        return func

    sig = inspect.signature(func)
    context_params: list[inspect.Parameter] = []
    remaining_params: list[inspect.Parameter] = []

    for param in sig.parameters.values():
        if _is_invocation_context_annotation(param.annotation):
            context_params.append(param)
            continue
        remaining_params.append(param)

    if not context_params:
        return func

    runtime_sig = sig.replace(parameters=remaining_params)
    setattr(func, "__typerplus_original_signature__", sig)
    setattr(func, "__typerplus_runtime_signature__", runtime_sig)
    setattr(
        func,
        "__typerplus_context_param_names__",
        tuple(param.name for param in context_params),
    )
    func.__signature__ = runtime_sig
    return func


def _default_logger_option(_: inspect.Parameter) -> ParameterInfo:
    return typer.Option(
        ...,
        "--verbose",
        "-v",
        count=True,
        help="Increase log verbosity (repeat for more detail).",
    )


def _default_invocation_factory(
    *,
    original: Callable[..., Any],
    target: Callable[..., Any],
    environment: InvocationEnvironment,
    call: InvocationCall,
    state: dict[str, Any] | None = None,
) -> Invocation:
    return Invocation(
        original=original,
        target=target,
        environment=environment,
        call=call,
        state=state or {},
    )


class Pipeline:
    """
    A Pythonic command middleware pipeline inspired by Flask/FastAPI ergonomics.

    - Decorators affect the function signature Typer inspects.
    - Middlewares wrap invoke-time behavior (pre/post).
    - Param-type hooks enrich or backfill Option metadata.
    """

    def __init__(
        self,
        *,
        decorators: Iterable[Decorator] | None = None,
        middlewares: Iterable[Middleware] | None = None,
        invocation_factory: InvocationFactory | None = None,
    ):
        self._decorators: list[Decorator] = list(decorators or [])
        self._middlewares: list[Middleware] = list(middlewares or [])
        self._param_hooks: list[Decorator] = []
        self._virtual_params: list[_VirtualParameter] = []
        self._invocation_factory: InvocationFactory = (
            invocation_factory or _default_invocation_factory
        )

    # Registration helpers
    def use(self, middleware: Middleware) -> "Pipeline":
        self._middlewares.append(middleware)
        return self

    def add_middleware(self, middleware: Middleware) -> "Pipeline":
        return self.use(middleware)

    def use_decorator(self, decorator: Decorator) -> "Pipeline":
        self._decorators.append(decorator)
        return self

    def add_signature_transform(self, decorator: Decorator) -> "Pipeline":
        return self.use_decorator(decorator)

    def inject_context(self) -> "Pipeline":
        """Ensure Typer context is injected into command signatures."""
        return self.use_decorator(_ensure_context_parameter)

    def set_invocation_factory(self, factory: InvocationFactory) -> "Pipeline":
        self._invocation_factory = factory
        return self

    def register_param_type(
        self,
        param_type: type,
        *,
        option_factory: Callable[[inspect.Parameter], ParameterInfo] | None,
        parser_factory: Callable[[], Any] | type | Any | None = None,
    ) -> "Pipeline":
        hook = _create_param_type_hook(param_type, option_factory, parser_factory)
        self._param_hooks.append(hook)
        return self

    def add_virtual_option(
        self,
        name: str,
        *,
        option: ParameterInfo | None = None,
        annotation_type: Any = bool,
        default: Any = False,
        state_key: str | None = None,
        store_in_state: bool = True,
    ) -> "Pipeline":
        """Expose an option to Typer without forwarding it to the user command."""

        if any(virtual.name == name for virtual in self._virtual_params):
            raise ValueError(f"Virtual option '{name}' is already registered.")

        option = option or _default_virtual_option(name, default=default)
        parameter = _create_virtual_option_parameter(
            name=name,
            option=option,
            annotation_type=annotation_type,
        )
        default_value = getattr(option, "default", inspect.Signature.empty)
        resolved_state_key: str | None = None
        if store_in_state:
            resolved_state_key = state_key or f"virtual:{name}"

        self._virtual_params.append(
            _VirtualParameter(
                name=name,
                parameter=parameter,
                state_key=resolved_state_key,
                default_value=default_value,
            )
        )
        return self

    def enable_logger(
        self,
        *,
        option_factory: Callable[[inspect.Parameter], ParameterInfo] | None = None,
        parser_factory: Callable[[], Any] | type | Any | None = None,
    ) -> "Pipeline":
        from .parser.logger import LoggerParser

        option_factory = option_factory or _default_logger_option
        parser_factory = parser_factory or LoggerParser
        return self.register_param_type(
            logging.Logger, option_factory=option_factory, parser_factory=parser_factory
        )

    # Building
    def build(
        self,
        func: Callable[..., Any],
        *,
        app: Any = None,
        name: str | None = None,
    ) -> Callable[..., Any]:
        """Return a callable to register with Typer."""

        original = func

        # Apply signature/metadata decorators in registration order (outermost first)
        decorated = func
        for dec in self._decorators:
            decorated = dec(decorated)

        for hook in self._param_hooks:
            decorated = hook(decorated)

        current_virtual_params = list(self._virtual_params)
        decorated = _apply_virtual_parameters(decorated, current_virtual_params)

        decorated = _ensure_invocation_context_parameter(decorated)

        # Ensure Typer can read the final signature
        ensure_signature(decorated)

        # Base handler makes the actual call
        def base(inv: Invocation) -> Any:
            return inv.invoke_target()

        # Compose invoke middlewares (last registered runs innermost)
        handler: CommandHandler = base
        for mw in reversed(self._middlewares):
            handler = mw(handler)

        # Adapter registered with Typer; signature must match `decorated`
        @wraps(decorated)
        def adapter(*args: Any, **kwargs: Any) -> Any:
            context = None
            get_context = getattr(typer, "get_current_context", None)
            if callable(get_context):
                try:
                    context = get_context(silent=True)
                except RuntimeError:
                    context = None
            if context is None:
                click_get_context = getattr(click, "get_current_context", None)
                if callable(click_get_context):
                    try:
                        context = click_get_context(silent=True)
                    except RuntimeError:
                        context = None
            environment = InvocationEnvironment(
                app=app,
                name=name,
                context=context,
            )
            call = InvocationCall(args=tuple(args), kwargs=dict(kwargs))
            inv = self._invocation_factory(
                original=original,
                target=decorated,
                environment=environment,
                call=call,
            )
            for virtual in current_virtual_params:
                if virtual.state_key:
                    value = inv.call.kwargs.get(virtual.name, virtual.default_value)
                    if value is inspect.Signature.empty:
                        value = None
                    inv.state[virtual.state_key] = value
            return handler(inv)

        # Guarantee Typer sees the signature from `decorated` even with wraps
        try:
            adapter.__signature__ = inspect.signature(decorated)
        except (TypeError, ValueError):
            pass

        return adapter


def _looks_like_context_param(param: inspect.Parameter) -> bool:
    if param.annotation in (typer.Context, click.Context):
        return True
    if param.name == "ctx" and param.annotation is inspect._empty:
        return True
    return False


def _ensure_context_parameter(func: Callable[..., Any]) -> Callable[..., Any]:
    """Ensure a Typer/click context parameter is present in the callable signature."""

    sig = inspect.signature(func)
    if any(_looks_like_context_param(param) for param in sig.parameters.values()):
        return func

    @wraps(func)
    def wrapper(ctx: typer.Context, *args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    ctx_param = inspect.Parameter(
        "ctx",
        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=typer.Context,
    )
    wrapper.__signature__ = sig.replace(
        parameters=[ctx_param, *sig.parameters.values()],
        return_annotation=sig.return_annotation,
    )
    return wrapper

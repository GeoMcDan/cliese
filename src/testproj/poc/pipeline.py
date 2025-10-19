from __future__ import annotations

import inspect
import logging
from functools import wraps
from typing import Any, Callable, Iterable

import typer
from typer.models import ParameterInfo

from ..annotation import TyperAnnotation
from .types import (
    CommandHandler,
    Decorator,
    Invocation,
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


def _default_logger_option(_: inspect.Parameter) -> ParameterInfo:
    return typer.Option(
        ...,
        "--verbose",
        "-v",
        count=True,
        help="Increase log verbosity (repeat for more detail).",
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
    ):
        self._decorators: list[Decorator] = list(decorators or [])
        self._middlewares: list[Middleware] = list(middlewares or [])
        self._param_hooks: list[Decorator] = []

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

    def enable_logger(
        self,
        *,
        option_factory: Callable[[inspect.Parameter], ParameterInfo] | None = None,
        parser_factory: Callable[[], Any] | type | Any | None = None,
    ) -> "Pipeline":
        from ..parser.logger import LoggerParser

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

        # Ensure Typer can read the final signature
        ensure_signature(decorated)

        # Base handler makes the actual call
        def base(inv: Invocation) -> Any:
            return inv.target(*inv.args, **inv.kwargs)

        # Compose invoke middlewares (last registered runs innermost)
        handler: CommandHandler = base
        for mw in reversed(self._middlewares):
            handler = mw(handler)

        # Adapter registered with Typer; signature must match `decorated`
        @wraps(decorated)
        def adapter(*args: Any, **kwargs: Any) -> Any:
            inv = Invocation(
                app=app,
                original=original,
                target=decorated,
                args=args,
                kwargs=kwargs,
                name=name,
            )
            return handler(inv)

        # Guarantee Typer sees the signature from `decorated` even with wraps
        try:
            adapter.__signature__ = inspect.signature(decorated)
        except (TypeError, ValueError):
            pass

        return adapter

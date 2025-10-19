from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable

import typer
from typer.models import ParameterInfo

from .pipeline import Pipeline
from .setup import get_pipeline
from .types import CommandHandler, Decorator, Invocation, Middleware


class ExtendedTyper(typer.Typer):
    """
    Typer subclass that composes a CLI middleware pipeline with Flask/FastAPI-like helpers.

    - Registration-time decorators shape the signature Typer inspects.
    - Invoke-time middlewares provide `before_invoke` / `after_invoke` hooks.
    - Param-type helpers (`enable_logger`, `register_param_type`) expose opinionated defaults.

    Consumers can stick to ergonomic `app.enable_logger()`, `@app.before_invoke`, etc.
    Advanced users can still pass a fully customised `Pipeline` instance.
    """

    def __init__(self, *args, pipeline: Pipeline | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._pipeline = pipeline

    @property
    def pipeline(self) -> Pipeline:
        return self._pipeline or get_pipeline()

    # Pythonic helpers -------------------------------------------------
    def add_middleware(self, middleware: Middleware) -> Middleware:
        """Attach invoke-time middleware to the underlying pipeline."""
        self.pipeline.add_middleware(middleware)
        return middleware

    def add_signature_transform(self, decorator: Decorator) -> Decorator:
        """Register a decorator that reshapes command signatures."""
        self.pipeline.add_signature_transform(decorator)
        return decorator

    def register_param_type(
        self,
        param_type: type,
        *,
        option_factory: Callable[[inspect.Parameter], ParameterInfo] | None = None,
        parser_factory: Callable[[], object] | type | object | None = None,
    ) -> "ExtendedTyper":
        """Expose Pipeline.register_param_type via the Typer facade."""
        self.pipeline.register_param_type(
            param_type,
            option_factory=option_factory,
            parser_factory=parser_factory,
        )
        return self

    def enable_logger(
        self,
        *,
        option_factory: Callable[[inspect.Parameter], ParameterInfo] | None = None,
        parser_factory: Callable[[], object] | type | object | None = None,
    ) -> "ExtendedTyper":
        """Enable Logger injection for this app's pipeline."""
        self.pipeline.enable_logger(
            option_factory=option_factory,
            parser_factory=parser_factory,
        )
        return self

    def before_invoke(
        self, func: Callable[[Invocation], Any]
    ) -> Callable[[Invocation], Any]:
        """Register a callable that runs before each command invocation."""

        def middleware(next_handler: CommandHandler) -> CommandHandler:
            def handler(inv: Invocation) -> Any:
                func(inv)
                return next_handler(inv)

            return handler

        self.add_middleware(middleware)
        return func

    def after_invoke(
        self, func: Callable[[Invocation, Any], Any]
    ) -> Callable[[Invocation, Any], Any]:
        """Register a callable that runs after each command invocation."""

        def middleware(next_handler: CommandHandler) -> CommandHandler:
            def handler(inv: Invocation) -> Any:
                result = next_handler(inv)
                func(inv, result)
                return result

            return handler

        self.add_middleware(middleware)
        return func

    @wraps(typer.Typer.command)
    def command(self, *args, **kwargs):
        base_decorator = super().command(*args, **kwargs)
        pipeline = self.pipeline

        def register(func: Callable[..., Any]) -> Callable[..., Any]:
            name = kwargs.get("name") or getattr(func, "__name__", None)
            wrapped = pipeline.build(func, app=self, name=name)
            # Typer registers the adapter; returns the wrapper Typer uses
            callback = base_decorator(wrapped)

            # Optional: event/callback hook opportunity (Pythonic pattern)
            # Users can still compose decorators on top of @app.command
            return callback

        return register

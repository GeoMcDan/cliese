from __future__ import annotations

from functools import wraps
from typing import Any, Callable

import typer

from .pipeline import Pipeline
from .setup import get_pipeline


class ExtendedTyper(typer.Typer):
    """
    Typer subclass that composes a CLI middleware pipeline.

    This remains Pythonic for consumers while providing OWIN/ASP.NET-style
    layering:
      - Registration-time decorators shape the function signature seen by Typer
      - Invoke-time middlewares wrap the function call with pre/post hooks

    Example usage:
        import testproj.poc as x

        p = x.Pipeline()
        p.use_decorator(my_sig_decorator)
        p.use(my_invoke_middleware)

        app = x.ExtendedTyper(pipeline=p)

        @app.command()
        def my_cmd(...):
            ...
    """

    def __init__(self, *args, pipeline: Pipeline | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._pipeline = pipeline

    @property
    def pipeline(self) -> Pipeline:
        return self._pipeline or get_pipeline()

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

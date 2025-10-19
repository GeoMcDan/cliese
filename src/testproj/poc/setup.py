from __future__ import annotations

import inspect
from typing import Any, Callable, Iterable

from typer.models import ParameterInfo

from .pipeline import Pipeline
from .types import Decorator, InvocationFactory, Middleware

_global_pipeline: Pipeline | None = None


def setup(
    *,
    decorators: Iterable[Decorator] | None = None,
    middlewares: Iterable[Middleware] | None = None,
    invocation_factory: InvocationFactory | None = None,
) -> Pipeline:
    """Create and set the global default pipeline."""
    global _global_pipeline
    _global_pipeline = Pipeline(
        decorators=decorators,
        middlewares=middlewares,
        invocation_factory=invocation_factory,
    )
    return _global_pipeline


def get_pipeline() -> Pipeline:
    """Get the global pipeline, creating a no-op instance if unset."""
    global _global_pipeline
    if _global_pipeline is None:
        _global_pipeline = Pipeline()
    return _global_pipeline


def _mutate_pipeline(action: Callable[[Pipeline], Any]) -> Pipeline:
    """Helper to coordinate global pipeline mutations for wrapper helpers."""
    pipeline = get_pipeline()
    action(pipeline)
    return pipeline


def use_middleware(mw: Middleware) -> Pipeline:
    return _mutate_pipeline(lambda pipeline: pipeline.use(mw))


def use_decorator(dec: Decorator) -> Pipeline:
    return _mutate_pipeline(lambda pipeline: pipeline.use_decorator(dec))


def use_invocation_factory(factory: InvocationFactory) -> Pipeline:
    """Replace the invocation factory on the global pipeline."""

    return _mutate_pipeline(lambda pipeline: pipeline.set_invocation_factory(factory))


def register_param_type(
    param_type: type,
    *,
    option_factory: Callable[[inspect.Parameter], ParameterInfo] | None = None,
    parser_factory: Callable[[], object] | type | object | None = None,
) -> Pipeline:
    """Register a custom parameter type on the global pipeline."""

    return _mutate_pipeline(
        lambda pipeline: pipeline.register_param_type(
            param_type,
            option_factory=option_factory,
            parser_factory=parser_factory,
        )
    )


def enable_logger(
    *,
    option_factory: Callable[[inspect.Parameter], ParameterInfo] | None = None,
    parser_factory: Callable[[], object] | type | object | None = None,
) -> Pipeline:
    """Convenience wrapper to enable Logger injection globally."""

    return _mutate_pipeline(
        lambda pipeline: pipeline.enable_logger(
            option_factory=option_factory,
            parser_factory=parser_factory,
        )
    )

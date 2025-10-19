from __future__ import annotations

from typing import Iterable

from .pipeline import Pipeline
from .types import Decorator, Middleware

_global_pipeline: Pipeline | None = None


def setup(
    *,
    decorators: Iterable[Decorator] | None = None,
    middlewares: Iterable[Middleware] | None = None,
) -> Pipeline:
    """Create and set the global default pipeline."""
    global _global_pipeline
    _global_pipeline = Pipeline(decorators=decorators, middlewares=middlewares)
    return _global_pipeline


def get_pipeline() -> Pipeline:
    """Get the global pipeline, creating a no-op instance if unset."""
    global _global_pipeline
    if _global_pipeline is None:
        _global_pipeline = Pipeline()
    return _global_pipeline


def use_middleware(mw: Middleware) -> Pipeline:
    p = get_pipeline()
    p.use(mw)
    return p


def use_decorator(dec: Decorator) -> Pipeline:
    p = get_pipeline()
    p.use_decorator(dec)
    return p

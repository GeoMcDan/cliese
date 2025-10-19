from __future__ import annotations

import inspect
import logging
from typing import Callable, Iterable

from typer.models import ParameterInfo

from .config import PipelineConfig
from .parser.logger import LoggerParser
from .pipeline import Pipeline, _default_logger_option
from .types import Decorator, InvocationFactory, Middleware

_global_pipeline: Pipeline | None = None
_pipeline_config: PipelineConfig = PipelineConfig()


def setup(
    *,
    config: PipelineConfig | None = None,
    decorators: Iterable[Decorator] | None = None,
    middlewares: Iterable[Middleware] | None = None,
    invocation_factory: InvocationFactory | None = None,
) -> Pipeline:
    """Create and set the global default pipeline."""
    global _pipeline_config, _global_pipeline

    if config is None:
        config = PipelineConfig()
        if decorators:
            config = config.add_decorators(decorators)
        if middlewares:
            config = config.add_middlewares(middlewares)
        config = config.set_invocation_factory(invocation_factory)
    else:
        if any(
            value is not None for value in (decorators, middlewares, invocation_factory)
        ):
            raise ValueError(
                "When providing a PipelineConfig, do not also supply decorators, "
                "middlewares, or invocation_factory arguments."
            )

    _pipeline_config = config
    _global_pipeline = _pipeline_config.to_pipeline()
    return _global_pipeline


def get_pipeline() -> Pipeline:
    """Get the global pipeline, creating a no-op instance if unset."""
    global _global_pipeline
    if _global_pipeline is None:
        _global_pipeline = _pipeline_config.to_pipeline()
    return _global_pipeline


def get_config() -> PipelineConfig:
    """Return the current global pipeline configuration."""

    return _pipeline_config


def _mutate_config(mutator: Callable[[PipelineConfig], PipelineConfig]) -> Pipeline:
    """Apply a configuration update and rebuild the global pipeline."""

    global _pipeline_config, _global_pipeline
    _pipeline_config = mutator(_pipeline_config)
    _global_pipeline = _pipeline_config.to_pipeline()
    return _global_pipeline


def use_middleware(mw: Middleware) -> Pipeline:
    return _mutate_config(lambda cfg: cfg.add_middleware(mw))


def use_decorator(dec: Decorator) -> Pipeline:
    return _mutate_config(lambda cfg: cfg.add_decorator(dec))


def inject_context() -> Pipeline:
    """Ensure the global pipeline injects Typer Context into commands."""

    return _mutate_config(lambda cfg: cfg.inject_context())


def use_invocation_factory(factory: InvocationFactory | None) -> Pipeline:
    """Replace the invocation factory on the global pipeline."""

    return _mutate_config(lambda cfg: cfg.set_invocation_factory(factory))


def register_param_type(
    param_type: type,
    *,
    option_factory: Callable[[inspect.Parameter], ParameterInfo] | None = None,
    parser_factory: Callable[[], object] | type | object | None = None,
) -> Pipeline:
    """Register a custom parameter type on the global pipeline."""

    return _mutate_config(
        lambda cfg: cfg.add_param_type(
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

    option_factory = option_factory or _default_logger_option
    parser_factory = parser_factory or LoggerParser

    return register_param_type(
        logging.Logger,
        option_factory=option_factory,
        parser_factory=parser_factory,
    )

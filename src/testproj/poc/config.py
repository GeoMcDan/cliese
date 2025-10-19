from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable, Iterable

from typer.models import ParameterInfo

from .types import Decorator, InvocationFactory, Middleware

if TYPE_CHECKING:
    from .pipeline import Pipeline


@dataclass(frozen=True)
class ParamTypeHook:
    """Configuration describing a Pipeline.register_param_type call."""

    param_type: type
    option_factory: Callable[[inspect.Parameter], ParameterInfo] | None = None
    parser_factory: Callable[[], object] | type | object | None = None

    def apply(self, pipeline: "Pipeline") -> None:
        pipeline.register_param_type(
            self.param_type,
            option_factory=self.option_factory,
            parser_factory=self.parser_factory,
        )


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable bundle of pipeline customisations."""

    decorators: tuple[Decorator, ...] = ()
    middlewares: tuple[Middleware, ...] = ()
    invocation_factory: InvocationFactory | None = None
    param_type_hooks: tuple[ParamTypeHook, ...] = ()

    def to_pipeline(self) -> "Pipeline":
        """Materialise a Pipeline instance based on this configuration."""

        from .pipeline import Pipeline

        pipeline = Pipeline(
            decorators=self.decorators,
            middlewares=self.middlewares,
            invocation_factory=self.invocation_factory,
        )
        for hook in self.param_type_hooks:
            hook.apply(pipeline)
        return pipeline

    def add_decorator(self, decorator: Decorator) -> "PipelineConfig":
        """Return a new config with decorator appended."""

        return replace(self, decorators=self.decorators + (decorator,))

    def add_decorators(self, decorators: Iterable[Decorator]) -> "PipelineConfig":
        decorators_tuple = tuple(decorators)
        if not decorators_tuple:
            return self
        return replace(self, decorators=self.decorators + decorators_tuple)

    def add_middleware(self, middleware: Middleware) -> "PipelineConfig":
        """Return a new config with middleware appended."""

        return replace(self, middlewares=self.middlewares + (middleware,))

    def add_middlewares(self, middlewares: Iterable[Middleware]) -> "PipelineConfig":
        middlewares_tuple = tuple(middlewares)
        if not middlewares_tuple:
            return self
        return replace(self, middlewares=self.middlewares + middlewares_tuple)

    def set_invocation_factory(
        self, factory: InvocationFactory | None
    ) -> "PipelineConfig":
        """Return a new config with updated invocation factory."""

        return replace(self, invocation_factory=factory)

    def add_param_type(
        self,
        param_type: type,
        *,
        option_factory: Callable[[inspect.Parameter], ParameterInfo] | None = None,
        parser_factory: Callable[[], object] | type | object | None = None,
    ) -> "PipelineConfig":
        """Return a new config with an additional param type hook."""

        hook = ParamTypeHook(
            param_type=param_type,
            option_factory=option_factory,
            parser_factory=parser_factory,
        )
        return replace(self, param_type_hooks=self.param_type_hooks + (hook,))

    def merge(self, other: "PipelineConfig") -> "PipelineConfig":
        """Merge two configs, concatenating decorators, middlewares and hooks."""

        return PipelineConfig(
            decorators=self.decorators + other.decorators,
            middlewares=self.middlewares + other.middlewares,
            invocation_factory=other.invocation_factory
            if other.invocation_factory is not None
            else self.invocation_factory,
            param_type_hooks=self.param_type_hooks + other.param_type_hooks,
        )

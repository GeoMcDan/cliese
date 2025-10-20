from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Callable, Iterable

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
class VirtualOptionConfig:
    """Configuration describing a Pipeline.add_virtual_option call."""

    name: str
    option: ParameterInfo | None = None
    annotation_type: Any = bool
    default: Any = False
    state_key: str | None = None
    store_in_state: bool = True

    def apply(self, pipeline: "Pipeline") -> None:
        pipeline.add_virtual_option(
            self.name,
            option=self.option,
            annotation_type=self.annotation_type,
            default=self.default,
            state_key=self.state_key,
            store_in_state=self.store_in_state,
        )


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable bundle of pipeline customisations."""

    decorators: tuple[Decorator, ...] = ()
    middlewares: tuple[Middleware, ...] = ()
    invocation_factory: InvocationFactory | None = None
    param_type_hooks: tuple[ParamTypeHook, ...] = ()
    virtual_options: tuple[VirtualOptionConfig, ...] = ()

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
        for option in self.virtual_options:
            option.apply(pipeline)
        return pipeline

    def add_decorator(self, decorator: Decorator) -> "PipelineConfig":
        """Return a new config with decorator appended."""

        return replace(self, decorators=self.decorators + (decorator,))

    def inject_context(self) -> "PipelineConfig":
        """Return a new config that ensures Typer context injection."""

        from .pipeline import _ensure_context_parameter

        return self.add_decorator(_ensure_context_parameter)

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

    def add_virtual_option(
        self,
        name: str,
        *,
        option: ParameterInfo | None = None,
        annotation_type: Any = bool,
        default: Any = False,
        state_key: str | None = None,
        store_in_state: bool = True,
    ) -> "PipelineConfig":
        """Return a new config with an additional virtual option registration."""

        virtual = VirtualOptionConfig(
            name=name,
            option=option,
            annotation_type=annotation_type,
            default=default,
            state_key=state_key,
            store_in_state=store_in_state,
        )
        return replace(self, virtual_options=self.virtual_options + (virtual,))

    def merge(self, other: "PipelineConfig") -> "PipelineConfig":
        """Merge two configs, concatenating decorators, middlewares and hooks."""

        return PipelineConfig(
            decorators=self.decorators + other.decorators,
            middlewares=self.middlewares + other.middlewares,
            invocation_factory=other.invocation_factory
            if other.invocation_factory is not None
            else self.invocation_factory,
            param_type_hooks=self.param_type_hooks + other.param_type_hooks,
            virtual_options=self.virtual_options + other.virtual_options,
        )

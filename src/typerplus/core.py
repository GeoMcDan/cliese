from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Type, Union

import typer
from typer.core import DEFAULT_MARKUP_MODE, TyperCommand
from typer.models import CommandFunctionType, Default, ParameterInfo

from .pipeline import Pipeline
from .setup import get_pipeline
from .types import (
    CommandHandler,
    Decorator,
    Invocation,
    InvocationFactory,
    Middleware,
)


class TyperPlus(typer.Typer):
    """
    Typer subclass that composes a CLI middleware pipeline with Flask/FastAPI-like helpers.

    - Registration-time decorators shape the signature Typer inspects.
    - Invoke-time middlewares provide `before_invoke` / `after_invoke` hooks.
    - Param-type helpers (`enable_logger`, `register_param_type`) expose opinionated defaults.

    Consumers can stick to ergonomic `app.enable_logger()`, `@app.before_invoke`, etc.
    Advanced users can still pass a fully customised `Pipeline` instance.
    """

    if TYPE_CHECKING:
        from typer.core import MarkupMode
        from typer.models import TyperGroup, TyperInfo

    def __init__(
        self,
        *,
        name: Optional[str] = Default(None),
        cls: Optional[Type[TyperGroup]] = Default(None),
        invoke_without_command: bool = Default(False),
        no_args_is_help: bool = Default(False),
        subcommand_metavar: Optional[str] = Default(None),
        chain: bool = Default(False),
        result_callback: Optional[Callable[..., Any]] = Default(None),
        # Command
        context_settings: Optional[Dict[Any, Any]] = Default(None),
        callback: Optional[Callable[..., Any]] = Default(None),
        help: Optional[str] = Default(None),
        epilog: Optional[str] = Default(None),
        short_help: Optional[str] = Default(None),
        options_metavar: str = Default("[OPTIONS]"),
        add_help_option: bool = Default(True),
        hidden: bool = Default(False),
        deprecated: bool = Default(False),
        add_completion: bool = True,
        # Rich settings
        rich_markup_mode: MarkupMode = Default(DEFAULT_MARKUP_MODE),
        rich_help_panel: Union[str, None] = Default(None),
        pretty_exceptions_enable: bool = True,
        pretty_exceptions_show_locals: bool = True,
        pretty_exceptions_short: bool = True,
        # TyperPlus
        pipeline: Pipeline | None = None,
    ):
        super().__init__(
            name=name,
            cls=cls,
            invoke_without_command=invoke_without_command,
            no_args_is_help=no_args_is_help,
            subcommand_metavar=subcommand_metavar,
            chain=chain,
            result_callback=result_callback,
            context_settings=context_settings,
            callback=callback,
            help=help,
            epilog=epilog,
            short_help=short_help,
            options_metavar=options_metavar,
            add_help_option=add_help_option,
            hidden=hidden,
            deprecated=deprecated,
            add_completion=add_completion,
            rich_markup_mode=rich_markup_mode,
            rich_help_panel=rich_help_panel,
            pretty_exceptions_enable=pretty_exceptions_enable,
            pretty_exceptions_show_locals=pretty_exceptions_show_locals,
            pretty_exceptions_short=pretty_exceptions_short,
        )
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

    def inject_context(self) -> "TyperPlus":
        """Ensure Typer Context is available to commands and middleware."""
        self.pipeline.inject_context()
        return self

    def set_invocation_factory(self, factory: InvocationFactory) -> "TyperPlus":
        """Swap the invocation factory used when commands execute."""
        self.pipeline.set_invocation_factory(factory)
        return self

    def register_param_type(
        self,
        param_type: type,
        *,
        option_factory: Callable[[inspect.Parameter], ParameterInfo] | None = None,
        parser_factory: Callable[[], object] | type | object | None = None,
    ) -> "TyperPlus":
        """Expose Pipeline.register_param_type via the Typer facade."""
        self.pipeline.register_param_type(
            param_type,
            option_factory=option_factory,
            parser_factory=parser_factory,
        )
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
    ) -> "TyperPlus":
        """Expose Pipeline.add_virtual_option via the Typer facade."""

        self.pipeline.add_virtual_option(
            name,
            option=option,
            annotation_type=annotation_type,
            default=default,
            state_key=state_key,
            store_in_state=store_in_state,
        )
        return self

    def enable_logger(
        self,
        *,
        option_factory: Callable[[inspect.Parameter], ParameterInfo] | None = None,
        parser_factory: Callable[[], object] | type | object | None = None,
    ) -> "TyperPlus":
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

    def command(
        self,
        name: Optional[str] = None,
        *,
        cls: Optional[Type[TyperCommand]] = None,
        context_settings: Optional[Dict[Any, Any]] = None,
        help: Optional[str] = None,
        epilog: Optional[str] = None,
        short_help: Optional[str] = None,
        options_metavar: str = "[OPTIONS]",
        add_help_option: bool = True,
        no_args_is_help: bool = False,
        hidden: bool = False,
        deprecated: bool = False,
        # Rich settings
        rich_help_panel: Union[str, None] = Default(None),
    ) -> Callable[[CommandFunctionType], CommandFunctionType]:
        base_decorator = super().command(
            name,
            cls=cls,
            context_settings=context_settings,
            help=help,
            epilog=epilog,
            short_help=short_help,
            options_metavar=options_metavar,
            add_help_option=add_help_option,
            no_args_is_help=no_args_is_help,
            hidden=hidden,
            deprecated=deprecated,
            rich_help_panel=rich_help_panel,
        )

        pipeline = self.pipeline

        def register(func: Callable[..., Any]) -> Callable[..., Any]:
            nonlocal name
            name = name or getattr(func, "__name__", None)
            wrapped = pipeline.build(func, app=self, name=name)
            # Typer registers the adapter; returns the wrapper Typer uses
            callback = base_decorator(wrapped)

            # Optional: event/callback hook opportunity (Pythonic pattern)
            # Users can still compose decorators on top of @app.command
            return callback

        return register

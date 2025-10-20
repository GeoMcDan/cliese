"""Project package exposing CLI pipeline utilities alongside legacy modules."""

from . import legacy
from .config import PipelineConfig
from .pipeline import Pipeline
from .setup import (
    add_virtual_option,
    enable_logger,
    get_config,
    get_pipeline,
    inject_context,
    register_param_type,
    setup,
    use_decorator,
    use_invocation_factory,
    use_middleware,
)
from .testing import TestApp
from .testing import runner as test_runner
from .typer_ext import ExtendedTyper
from .types import (
    CommandContext,
    CommandHandler,
    Invocation,
    InvocationContext,
    InvocationFactory,
    Middleware,
)

__all__ = [
    "Invocation",
    "InvocationContext",
    "CommandContext",
    "InvocationFactory",
    "CommandHandler",
    "Middleware",
    "PipelineConfig",
    "Pipeline",
    "setup",
    "get_config",
    "get_pipeline",
    "inject_context",
    "register_param_type",
    "add_virtual_option",
    "use_decorator",
    "use_invocation_factory",
    "use_middleware",
    "enable_logger",
    "ExtendedTyper",
    "TestApp",
    "test_runner",
    "legacy",
]

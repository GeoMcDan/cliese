from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable

from click import ParamType

HookSpec = Callable[[str, object], None]


@dataclass
class RegistrationContext:
    event_handler: HookSpec | None = field(default=None, kw_only=True)
    decorator: Any = field(default=None, kw_only=True)
    extensions: MappingProxyType[str, list[object]] = field(
        default_factory=lambda: defaultdict(list), kw_only=True
    )
    param_types: MappingProxyType[Any, Any] = field(default_factory=dict, kw_only=True)

    def register_decorator(self, decorator):
        self.decorator = decorator

    def register_handler(self, event_handler: HookSpec):
        self.event_handler = event_handler

    def register_extension(self, ext_key: str, ext: object):
        self.extensions[ext_key].append(ext)

    def add_param_type(self, param: Any, parser: ParamType):
        if not parser:
            raise ValueError("parser must be not be None")

        if param in self.param_types:
            raise ValueError(f"A parser has already been registered for {param!r}")

        self.param_types[param] = parser


# TODO: consider thread local storage if we ever go multi-threaded
_global_context = RegistrationContext()


def add_param_type(param: Any, parser: ParamType):
    global _global_context
    _global_context.add_param_type(param, parser)


def register_extension(ext_key: str, ext: object):
    global _global_context
    _global_context.register_extension(ext_key, ext)


def register_handler(func: HookSpec):
    global _global_context
    _global_context.register_handler(func)


def register_decorator(decorator):
    global _global_context
    _global_context.register_decorator(decorator)


@contextmanager
def registration_context():
    global _global_context
    prev_context = _global_context
    context = RegistrationContext()

    _global_context = context
    yield context
    _global_context = prev_context

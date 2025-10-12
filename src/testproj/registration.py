from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable

HookSpec = Callable[[str, object], None]


@dataclass
class RegistrationContext:
    event_handler: HookSpec | None = field(default=None, kw_only=True)
    decorator: Any = field(default=None, kw_only=True)
    extensions: MappingProxyType[str, list[object]] = field(
        default_factory=lambda: defaultdict(list), kw_only=True
    )

    def register_decorator(self, decorator):
        self.decorator = decorator

    def register_handler(self, event_handler: HookSpec):
        self.event_handler = event_handler

    def register_extension(self, ext_key: str, ext: object):
        self.extensions[ext_key].append(ext)


_global_context = RegistrationContext()


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

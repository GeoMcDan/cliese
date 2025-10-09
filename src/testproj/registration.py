from contextlib import contextmanager
from typing import Callable

HookSpec = Callable[[str, object], None]

_func: HookSpec = None
_decorator = None


@contextmanager
def register_decorator(decorator):
    global _decorator
    prevd = _decorator

    _decorator = decorator
    yield
    _decorator = prevd


@contextmanager
def register(func: HookSpec):
    global _func
    prevf = _func

    _func = func
    yield
    _func = prevf

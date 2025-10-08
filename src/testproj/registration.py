from contextlib import contextmanager
from typing import Callable

HookSpec = Callable[[str, object], None]

_func: HookSpec = None


@contextmanager
def register(func: HookSpec):
    global _func
    prevf = _func

    _func = func
    yield
    _func = prevf

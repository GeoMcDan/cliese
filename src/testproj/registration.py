from contextlib import contextmanager

_func = None


@contextmanager
def register(func):
    global _func
    prevf = _func

    _func = func
    yield
    _func = prevf

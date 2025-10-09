from functools import wraps
from typing import cast

import typer

from testproj import registration

NO_RESULT = object()


class ExtendedTyper(typer.Typer):
    @wraps(typer.Typer.__init__)
    def __init__(self, *args, **kwargs):
        extension = kwargs.pop("register", self.__class__.get_registration_func())
        decorator = kwargs.pop("decorate", self.__class__.get_decorator())
        self.extension = cast(registration.HookSpec, extension)
        self.decorator = decorator
        super().__init__(*args, **kwargs)

    @classmethod
    def get_registration_func(cls) -> registration.HookSpec:
        return registration._func

    @classmethod
    def get_decorator(cls):
        return registration._decorator

    def register(self, func: registration.HookSpec):
        self.extension = func

    def register_decorator(self, decorator):
        self.decorator = decorator

    @wraps(typer.Typer.command)
    def command(self, *args, **kwargs):
        extension = cast(object, kwargs.pop("register", self.extension))
        decorator = kwargs.pop("register_decorator", self.decorator)
        base_decorator = super().command(*args, **kwargs)

        def extension_wrapper(func):
            def wrapper(*args_, **kwargs_):
                if extension:
                    extension("pre-invoke", (args_, kwargs_))
                result = func(*args_, **kwargs_)
                return result

            return wrapper

        def _decorate(func):
            @base_decorator
            @wraps(func)
            def wrapper(*args_, **kwargs_):
                _func = extension_wrapper(func)
                if decorator:
                    _func = decorator(_func)
                result = _func(*args_, **kwargs_)
                raise typer.Exit(result)

            return wrapper

        return _decorate

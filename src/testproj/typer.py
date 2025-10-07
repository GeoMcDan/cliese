from functools import wraps

import typer

from testproj import registration


class ExtendedTyper(typer.Typer):
    @wraps(typer.Typer.__init__)
    def __init__(self, *args, **kwargs):
        self.extension = kwargs.pop("register", self.__class__.get_registration_func())
        super().__init__(*args, **kwargs)

    @classmethod
    def get_registration_func(cls):
        return registration._func

    def register(self, func):
        self.extension = func

    @wraps(typer.Typer.command)
    def command(self, *args, **kwargs):
        extension = kwargs.pop("register", self.extension)

        decorator = super().command(*args, **kwargs)

        def _decorator(func):
            @wraps(func)
            def wrapper(*args_, **kwargs_):
                # placeholder extension invocation
                # raise Exception("testing")
                extension()
                return func(*args_, **kwargs_)

            return decorator(wrapper)

        return _decorator

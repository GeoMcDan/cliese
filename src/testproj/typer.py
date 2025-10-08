from functools import wraps
from typing import cast

import typer

from testproj import registration

NO_RESULT = object()


class ExtendedTyper(typer.Typer):
    @wraps(typer.Typer.__init__)
    def __init__(self, *args, **kwargs):
        extension = kwargs.pop("register", self.__class__.get_registration_func())
        self.extension = cast(registration.HookSpec, extension)
        super().__init__(*args, **kwargs)

    @classmethod
    def get_registration_func(cls) -> registration.HookSpec:
        return registration._func

    def register(self, func: registration.HookSpec):
        self.extension = func

    @wraps(typer.Typer.command)
    def command(self, *args, **kwargs):
        extension = cast(registration.HookSpec, kwargs.pop("register", self.extension))
        base_decorator = super().command(*args, **kwargs)

        def _decorate(func):
            @base_decorator
            @wraps(func)
            def wrapper(*args_, **kwargs_):
                # CONSIDER:
                # instead of pre-invoke/post-invoke event hooks
                # instead I could pass the wrapper function to the hook
                # If implementer wanted to inspect args/kwargs or return value, they could
                extension("pre-invoke", (args_, kwargs_))

                # implementation is getting heavy...
                # should TRY...EXCEPT be part of hook?
                # should result handling be part of hook?
                result = NO_RESULT
                try:
                    # Invoke command target function
                    result = func(*args_, **kwargs_)
                    raise typer.Exit(result)
                except Exception as e:
                    extension("invoke-error", e)
                    raise
                finally:
                    if result is not NO_RESULT:
                        extension("post-invoke", result)

            # return base_decorator(wrapper)
            return wrapper

        return _decorate

from functools import wraps
from typing import cast

import typer

from testproj import registration

NO_RESULT = object()


# TODO: Provide a protocol for this, update references,
# the result to exit code is temporary default behavior for convenience now.
class CommandResult:
    def __init__(self, result):
        self.result = result
        self._exit_code = result if isinstance(result, int) else 0

    @property
    def exit_code(self) -> int:
        return self._exit_code

    @exit_code.setter
    def exit_code(self, value: int):
        self._exit_code = value

    def __repr__(self):
        return f"CommandResult(result={self.result}, exit_code={self.exit_code})"


class ExtendedTyper(typer.Typer):
    @wraps(typer.Typer.__init__)
    def __init__(self, *args, **kwargs):
        event_handler = kwargs.pop(
            "event_handler", self.__class__.get_registration_func()
        )
        decorator = kwargs.pop("decorate", self.__class__.get_decorator())
        self.event_handler = cast(registration.HookSpec, event_handler)
        self.decorator = decorator
        super().__init__(*args, **kwargs)

    @classmethod
    def get_registration_func(cls) -> registration.HookSpec:
        return registration._global_context.event_handler

    @classmethod
    def get_decorator(cls):
        return registration._global_context.decorator

    def register(self, event_handler: registration.HookSpec, /):
        self.event_handler = event_handler

    def register_decorator(self, decorator):
        self.decorator = decorator

    def use_extension(self, key: str):
        self.event_handler = registration._global_context.extensions[key]

    @wraps(typer.Typer.command)
    def command(self, *args, **kwargs):
        event_handler = cast(object, kwargs.pop("event_handler", self.event_handler))
        decorator = kwargs.pop("register_decorator", self.decorator)
        base_decorator = super().command(*args, **kwargs)

        def extension_wrapper(func):
            def wrapper(*args_, **kwargs_):
                if event_handler:
                    event_handler("pre-invoke", (args_, kwargs_))

                result = func(*args_, **kwargs_)
                command_result = CommandResult(result)

                if event_handler:
                    # TODO: think about a context object, it would include an optional return result
                    # as it is return None is ambiguous, use a sentinal to indicate explicitly no result
                    event_handler("post-invoke", (args_, kwargs_, command_result))

                return command_result

            if event_handler:
                wrapper_result = event_handler("process_command", wrapper)
            else:
                wrapper_result = None
            return wrapper_result or wrapper

        def _decorate(func):
            @base_decorator
            @wraps(func)
            def wrapper(*args_, **kwargs_):
                _func = extension_wrapper(func)
                if decorator:
                    _func = decorator(_func)

                result = _func(*args_, **kwargs_)

                if result and isinstance(result, CommandResult):
                    raise typer.Exit(result.exit_code)
                elif result and result is int:
                    raise typer.Exit(result)
                else:
                    raise Exception("What is this result?")

            return wrapper

        return _decorate

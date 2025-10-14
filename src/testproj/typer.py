import inspect
from functools import wraps
from logging import getLogger
from typing import Iterable, cast

import typer

from testproj import registration

logger = getLogger(__name__)
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


class _EventDispatch:
    def __init__(self, event_handler):
        # logger.debug("event_handler: %s (%s)", event_handler, type(event_handler))
        self.handlers = []
        if isinstance(event_handler, Iterable):
            self.handlers = event_handler
        elif event_handler is not None:
            self.handlers = [event_handler]
        # logger.debug("self.handler: %s (%s)", self.handlers, type(self.handlers))

    def __call__(self, *args, **kwargs):
        for handler in self.handlers:
            # logger.debug("Handler: %s", handler)
            handler(*args, **kwargs)


class ExtendedTyper(typer.Typer):
    event_dispatch = _EventDispatch

    @wraps(typer.Typer.__init__)
    def __init__(self, *args, **kwargs):
        event_handler = kwargs.pop(
            "event_handler", self.__class__.get_registration_func()
        )
        decorator = kwargs.pop("decorate", self.__class__.get_decorator())
        self.event_handler = cast(registration.HookSpec, event_handler)
        self.decorator = decorator
        self.extension = kwargs.pop("extension", self.__class__.get_extension())
        super().__init__(*args, **kwargs)

    @classmethod
    def get_registration_func(cls) -> registration.HookSpec:
        return registration._global_context.event_handler

    @classmethod
    def get_decorator(cls):
        return registration._global_context.decorator

    @classmethod
    def get_extension(cls):
        return registration._global_context.extensions

    def register(self, event_handler: registration.HookSpec, /):
        self.event_handler = event_handler

    def register_decorator(self, decorator):
        self.decorator = decorator

    def use_extension(self, key: str):
        if key not in registration._global_context.extensions:
            raise KeyError(f"No extension registered for key: {key}")
        self.event_handler = registration._global_context.extensions[key]

    @wraps(typer.Typer.command)
    def command(self, *args, **kwargs):
        event_handler = self.event_dispatch(
            kwargs.pop("event_handler", self.event_handler)
        )
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

            return wrapper

        def _decorate(func):
            def _temp_int(logger: int):
                pass

            @wraps(func)
            @base_decorator
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

            # this will get run all commands on the full ExtendedTyper app
            # so we need to filter to what we are decorating
            isany = False
            wrapper_command = None
            for cmd in self.registered_commands:
                if cmd.callback != wrapper:
                    logger.debug(
                        "continuing after %s%s",
                        cmd.callback.__name__,
                        inspect.signature(cmd.callback),
                    )
                    continue
                wrapper_command = cmd.callback
                isany = True
            else:
                assert isany

            assert wrapper is wrapper_command
            event_handler("command", (self, wrapper))
            return wrapper

        return _decorate

import inspect
from functools import wraps
from logging import getLogger
from typing import Any, Iterable, Protocol, Type

import typer

from . import registration
from .registration import RegistrationContext

logger = getLogger(__name__)
NO_RESULT = object()


class CommandResultProtocol(Protocol):
    result: Any
    exit_code: int


class CommandResult(CommandResultProtocol):
    def __init__(self, result):
        self.result = result

        match result:
            case None:
                self._exit_code = 0
            case int():
                self._exit_code = result
            case _:
                self._exit_code = NO_RESULT

    @property
    def exit_code(self) -> int:
        return self._exit_code

    @exit_code.setter
    def exit_code(self, value: int):
        match value:
            case int():
                self._exit_code = value
            case _:
                raise ValueError("exit_code must be int")

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


def _reg_context():
    return registration._global_context


class ExtendedTyper(typer.Typer):
    # "new is glue", as they say
    cls_event_dispatch: Type[_EventDispatch] = _EventDispatch
    cls_command_result: Type[CommandResultProtocol] = CommandResult

    @wraps(typer.Typer.__init__)
    def __init__(self, *args, **kwargs):
        reg_context = _reg_context()
        self.registration_context = (
            kwargs.pop("registration_context", None) or reg_context
        )
        self.event_handler = (
            kwargs.pop("event_handler", None) or reg_context.event_handler
        )
        self.decorator = kwargs.pop("decorate", None) or reg_context.decorator
        self.extension = kwargs.pop("extension", None) or reg_context.extensions

        super().__init__(*args, **kwargs)

    @classmethod
    def get_registration_func(cls) -> registration.HookSpec:
        return _reg_context().event_handler

    @classmethod
    def get_decorator(cls):
        return _reg_context().decorator

    @classmethod
    def get_extension(cls):
        return _reg_context().extensions

    @property
    def reg_context(self):
        return self.registration_context

    def register(self, event_handler: registration.HookSpec, /):
        self.event_handler = event_handler

    def register_decorator(self, decorator):
        self.decorator = decorator

    def use_context(self, registration_context: RegistrationContext):
        self.registration_context = registration_context

    def use_extension(self, key: str):
        if key not in self.registration_context.extensions:
            raise KeyError(f"No extension registered for key: {key}")
        self.event_handler = self.registration_context.extensions[key]

    @wraps(typer.Typer.command)
    def command(self, *args, **kwargs):
        # TODO: are we working with lists now? replace or append
        # this impacts the pop/default behavior
        event_handler = self.cls_event_dispatch(
            kwargs.pop("event_handler", self.event_handler)
        )
        decorator = kwargs.pop("register_decorator", self.decorator)
        base_decorator = super().command(*args, **kwargs)

        def extension_wrapper(func):
            def wrapper(*args_, **kwargs_):
                if event_handler:
                    event_handler("pre-invoke", (args_, kwargs_))

                result = func(*args_, **kwargs_)
                command_result = self.cls_command_result(result)

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
                if result.exit_code is not NO_RESULT:
                    raise typer.Exit(result.exit_code)

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

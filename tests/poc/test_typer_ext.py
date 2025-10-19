import inspect
import logging
from typing import Annotated, Any, get_args, get_origin

import click
import typer
from typer.models import ParameterInfo
from typer.testing import CliRunner

from testproj.parser.logger import LoggerParser
from testproj.poc import ExtendedTyper, Pipeline

runner = CliRunner()


def test_extended_typer_uses_pipeline_decorator_and_middleware():
    """ExtendedTyper uses pipeline: decorator exposes option and middleware wraps execution."""
    events: list[str] = []

    def dec(func):
        # Registration-time: publish a signature that adds --x while
        # forwarding the call unchanged. Printing x here makes the effect
        # observable in stdout for the assertion below.
        def template(x: int = 0): ...

        def wrapper(*args, **kwargs):
            print(kwargs.get("x", 0))
            return func()

        wrapper.__signature__ = inspect.signature(template)
        return wrapper

    # Invoke-time: simple pre/post wrapper to show middleware ordering works
    # with ExtendedTyper in the same way as with bare Pipeline.
    def mw(next):
        def handler(inv):
            events.append("pre")
            r = next(inv)
            events.append("post")
            return r

        return handler

    # Compose decorator + middleware and pass explicitly to the app. If no
    # pipeline is provided, ExtendedTyper would use the global one.
    pipeline = Pipeline().use_decorator(dec).use(mw)
    app = ExtendedTyper(pipeline=pipeline)

    @app.command()
    def hello():
        print("HELLO")

    # Typer sees --x from the decorator-altered signature; mw wraps around the
    # call, recording events, while the decorated function prints the value.
    res = runner.invoke(app, ["--x", "7"])
    if res.exception:
        raise res.exception

    # stdout prints x first (from decorator), then the body; middleware ran.
    assert "7" in res.stdout
    assert "HELLO" in res.stdout
    assert events == ["pre", "post"]


def _option_from_annotation(annotation):
    if get_origin(annotation) is Annotated:
        _, *meta = get_args(annotation)
        for item in meta:
            if isinstance(item, ParameterInfo):
                return item
    return None


def test_extended_typer_enable_logger_adds_option_and_parser():
    captured = {}
    app = ExtendedTyper()
    app.enable_logger()

    @app.command()
    def hello(logger: logging.Logger):
        captured["level"] = logger.level
        print(logger.level)

    command = app.registered_commands[0]
    sig = inspect.signature(command.callback)
    option = _option_from_annotation(sig.parameters["logger"].annotation)
    assert option is not None
    assert isinstance(option.click_type, LoggerParser)

    result = runner.invoke(app, ["-vv"])
    if result.exception:
        raise result.exception

    # LoggerParser maps -vv -> INFO
    assert captured["level"] == logging.INFO


def test_extended_typer_before_after_invoke_helpers():
    order: list[str] = []
    app = ExtendedTyper()

    @app.before_invoke
    def capture_before(inv: Any):
        order.append("before")

    @app.after_invoke
    def capture_after(inv: Any, result: Any):
        order.append("after")

    @app.command()
    def hello():
        order.append("body")

    result = runner.invoke(app)
    if result.exception:
        raise result.exception

    assert order == ["before", "body", "after"]


def test_extended_typer_register_param_type_delegates():
    class Token(str):
        pass

    class TokenParser(click.ParamType):
        name = "token"

        def convert(self, value, parameter, ctx):
            return Token(value[::-1])

    app = ExtendedTyper()
    app.register_param_type(
        Token,
        option_factory=lambda param: typer.Option(..., "--token"),
        parser_factory=TokenParser,
    )

    captured = {}

    @app.command()
    def hello(token: Token | None = None):
        captured["token"] = token

    command = app.registered_commands[0]
    sig = inspect.signature(command.callback)
    option = _option_from_annotation(sig.parameters["token"].annotation)
    assert isinstance(option.click_type, TokenParser)

    result = runner.invoke(app, ["--token", "abc"])
    if result.exception:
        raise result.exception

    assert captured["token"] == "cba"

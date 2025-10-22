import inspect
import logging
from functools import wraps
from typing import Annotated, Any, get_args, get_origin

import click
import typer
from typer.models import ParameterInfo
from typer.testing import CliRunner

from typerplus import Pipeline, TyperPlus
from typerplus.parser.logger import LoggerParser
from typerplus.types import Invocation

runner = CliRunner()


def test_typer_plus_uses_pipeline_decorator_and_middleware():
    """TyperPlus uses pipeline: decorator exposes option and middleware wraps execution."""
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
    # with TyperPlus in the same way as with bare Pipeline.
    def mw(next):
        def handler(inv):
            events.append("pre")
            r = next(inv)
            events.append("post")
            return r

        return handler

    # Compose decorator + middleware and pass explicitly to the app. If no
    # pipeline is provided, TyperPlus would use the global one.
    pipeline = Pipeline().use_decorator(dec).use(mw)
    app = TyperPlus(pipeline=pipeline)

    @app.command()
    def hello():
        print("HELLO")

    # Typer sees --x from the decorator-altered signature; mw wraps around the
    # call, recording events, while the decorated function prints the value.
    res = runner.invoke(app, ["--x", "7"])
    if res.exception:
        raise res.exception

    # stdout prints x first (from decorator), then the body; middleware ran.
    assert "7" in res.output
    assert "HELLO" in res.output
    assert events == ["pre", "post"]


def _option_from_annotation(annotation):
    if get_origin(annotation) is Annotated:
        _, *meta = get_args(annotation)
        for item in meta:
            if isinstance(item, ParameterInfo):
                return item
    return None


def test_typer_plus_enable_logger_adds_option_and_parser():
    captured = {}
    app = TyperPlus()
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

    # LoggerParser maps -vv -> DEBUG
    assert captured["level"] == logging.DEBUG


def test_typer_plus_before_after_invoke_helpers():
    order: list[str] = []
    app = TyperPlus()

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


def test_typer_plus_register_param_type_delegates():
    class Token(str):
        pass

    class TokenParser(click.ParamType):
        name = "token"

        def convert(self, value, parameter, ctx):
            return Token(value[::-1])

    app = TyperPlus()
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


def get_param(app, param_name):
    command = app.registered_commands[0]
    command_sig = inspect.signature(command.callback)
    return command_sig.parameters[param_name]


def test_typer_plus_virtual_option_exposed_and_captured():
    pipeline = Pipeline()
    app = TyperPlus(pipeline=pipeline)
    app.add_virtual_option(
        "what_if",
        option=typer.Option(False, "--what-if", help="Dry run"),
    )

    seen: dict[str, Any] = {}
    captured: dict[str, Any] = {}

    @app.before_invoke
    def capture(inv: Invocation):
        seen["kwargs"] = dict(inv.kwargs)
        seen["state"] = inv.state.get("virtual:what_if")

    @app.command()
    def run(value: int):
        captured["value"] = value

    result = runner.invoke(app, ["5", "--what-if"])
    if result.exception:
        raise result.exception

    assert captured["value"] == 5
    assert seen["kwargs"]["what_if"] is True
    assert seen["state"] is True

    what_if_param = get_param(app, "what_if")
    what_if_option = what_if_param.default
    assert isinstance(what_if_option, ParameterInfo)
    assert "--what-if" in what_if_option.param_decls


def test_typer_plus_set_invocation_factory_applies_custom_factory():
    app = TyperPlus()
    created: list[Invocation] = []
    seen: list[str] = []
    contexts: list[Any] = []

    def factory(
        *,
        original,
        target,
        state=None,
        environment,
        call,
    ) -> Invocation:
        contexts.append(environment.context)
        inv = Invocation(
            original=original,
            target=target,
            environment=environment,
            call=call,
            state=state or {},
        )
        inv.state["flag"] = "ext"
        created.append(inv)
        return inv

    app.set_invocation_factory(factory)

    @app.after_invoke
    def capture(inv: Invocation, result: Any):
        seen.append(inv.state.get("flag"))

    @app.command()
    def hello():
        return "ok"

    result = runner.invoke(app)
    if result.exception:
        raise result.exception

    assert created and created[0].state["flag"] == "ext"
    assert seen == ["ext"]
    assert contexts and contexts[0] is not None


def test_typer_plus_integration_provides_typer_context():
    decorator_contexts: list[click.Context] = []
    middleware_contexts: list[click.Context] = []
    invocation_contexts: list[click.Context] = []
    invoked: list[bool] = []

    def context_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ctx = click.get_current_context()
            assert ctx is not None
            assert isinstance(ctx, click.Context)
            decorator_contexts.append(ctx)
            return func(*args, **kwargs)

        return wrapper

    def context_middleware(next_handler):
        def handler(inv: Invocation):
            ctx = inv.context
            assert ctx is not None
            assert isinstance(ctx, click.Context)
            assert ctx is inv.environment.context
            middleware_contexts.append(ctx)
            return next_handler(inv)

        return handler

    pipeline = Pipeline().use_decorator(context_decorator).use(context_middleware)
    app = TyperPlus(pipeline=pipeline)
    app.inject_context()

    @app.command()
    def hello():
        ctx = click.get_current_context()
        assert ctx is not None
        assert isinstance(ctx, click.Context)
        invocation_contexts.append(ctx)
        invoked.append(True)
        return "done"

    result = runner.invoke(app)
    if result.exception:
        raise result.exception

    assert invoked == [True]
    assert decorator_contexts and middleware_contexts and invocation_contexts
    assert decorator_contexts[0] is middleware_contexts[0] is invocation_contexts[0]

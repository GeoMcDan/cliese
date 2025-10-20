import inspect
import logging
from typing import Annotated, Any, get_args, get_origin

import click
from typer import Option
from typer.models import ParameterInfo
from typer.testing import CliRunner

from typerplus import ExtendedTyper
from typerplus.parser.logger import LoggerParser
from typerplus.pipeline import Pipeline, _instantiate_parser
from typerplus.types import CommandContext, Invocation, InvocationContext


def test_pipeline_decorator_affects_signature():
    """Pipeline decorator updates the wrapped function's signature via __signature__."""

    # "user" represents the developer's original command function. It has no
    # parameters; the pipeline should be able to expose additional CLI options
    # by changing the visible signature Typer inspects at registration time,
    # without changing the function body or behavior.
    def user():
        return "ok"

    def dec(func):
        # Registration-time decorator: it adjusts only how the function LOOKS
        # (its signature), not what it does. Typer will reflect this signature
        # and expose a corresponding option (--x) on the CLI.
        def template(x: int = 0): ...

        # Forwarding wrapper; for this test we ignore provided args/kwargs and
        # just call the original function to prove behavior is unchanged.
        def wrapper(*args, **kwargs):
            return func()

        # Publish the template's signature so reflection shows "(x: int = 0)".
        wrapper.__signature__ = inspect.signature(template)
        return wrapper

    p = Pipeline().use_decorator(dec)

    # build() constructs an adapter Typer will register:
    #  - applies the decorator to get a "decorated" target with the new
    #    signature
    #  - returns an adapter whose __signature__ mirrors the decorated target
    #    so Typer sees the added "x: int = 0" parameter
    wrapped = p.build(user)

    # The adapter should advertise the decorated signature exactly.
    sig = inspect.signature(wrapped)
    assert str(sig) == "(x: int = 0)"
    assert wrapped() == "ok"


def test_pipeline_middleware_order_and_state():
    """Middleware executes in order and shares/updates state around the user call."""
    order: list[str] = []

    # Middleware A runs first (outermost). It records pre/post markers and
    # seeds state so inner middleware(s) can read/extend it.
    def mw_a(next):
        def handler(inv):
            order.append("a_pre")
            inv.state["a"] = 1
            r = next(inv)
            order.append("a_post")
            return r

        return handler

    # Middleware B runs second (inner), sees state from A, and appends to it.
    def mw_b(next):
        def handler(inv):
            order.append("b_pre")
            inv.state["b"] = inv.state.get("a", 0) + 1
            r = next(inv)
            order.append("b_post")
            return r

        return handler

    # The developer's original command function. The middlewares wrap around
    # this call, producing the expected pre/call/post order.
    def user():
        order.append("call")
        return "ok"

    # Register A then B: A is outer, B is inner. build() composes the chain
    # so that invocation order is A.pre -> B.pre -> user -> B.post -> A.post.
    p = Pipeline().use(mw_a).use(mw_b)
    wrapped = p.build(user)
    result = wrapped()
    assert result == "ok"
    assert order == ["a_pre", "b_pre", "call", "b_post", "a_post"]


def _option_from_annotation(annotation):
    if get_origin(annotation) is Annotated:
        _, *meta = get_args(annotation)
        for item in meta:
            if isinstance(item, ParameterInfo):
                return item
    return None


def test_pipeline_enable_logger_adds_option_when_missing():
    pipeline = Pipeline().enable_logger()

    def user(logger: logging.Logger | None = None):
        return logger

    wrapped = pipeline.build(user)
    sig = inspect.signature(wrapped)
    param = sig.parameters["logger"]
    option = _option_from_annotation(param.annotation)

    assert option is not None
    assert isinstance(option.click_type, LoggerParser)
    # Option default should be available for Typer to treat as optional.
    assert getattr(option, "count", False)


def test_pipeline_enable_logger_updates_existing_option():
    option = Option("--log", "-l", count=True, help="Custom logger option")

    def user(logger: Annotated[logging.Logger | None, option] = None):
        return logger

    pipeline = Pipeline().enable_logger()
    wrapped = pipeline.build(user)
    sig = inspect.signature(wrapped)
    param = sig.parameters["logger"]
    extracted = _option_from_annotation(param.annotation)

    assert extracted is option
    assert isinstance(option.click_type, LoggerParser)


def test_pipeline_register_param_type_custom_parser():
    class Token(str):
        pass

    class TokenParser(click.ParamType):
        name = "token"

        def convert(self, value, parameter, ctx):
            return Token(value.upper())

    def option_factory(param: inspect.Parameter) -> ParameterInfo:
        return Option(..., "--token", "-t", help=f"{param.name} token")

    pipeline = Pipeline().register_param_type(
        Token,
        option_factory=option_factory,
        parser_factory=TokenParser,
    )

    def user(token: Token | None = None):
        return token

    wrapped = pipeline.build(user)
    sig = inspect.signature(wrapped)
    param = sig.parameters["token"]
    option = _option_from_annotation(param.annotation)

    assert option is not None
    assert isinstance(option.click_type, TokenParser)
    assert param.default is None


def test_instantiate_parser_none_returns_none():
    assert _instantiate_parser(None) is None


def test_instantiate_parser_callable_invoked():
    calls: list[str] = []

    def factory():
        calls.append("called")
        return {"parser": True}

    result = _instantiate_parser(factory)
    assert result == {"parser": True}
    assert calls == ["called"]


def test_pipeline_set_invocation_factory_replaces_invocation():
    pipeline = Pipeline()
    created: list[Invocation] = []
    seen_flags: list[str] = []

    def factory(
        *,
        original,
        target,
        environment,
        call,
        state=None,
    ) -> Invocation:
        inv = Invocation(
            original=original,
            target=target,
            environment=environment,
            call=call,
            state=state or {},
        )
        inv.state["factory"] = "custom"
        created.append(inv)
        return inv

    def capture(next_handler):
        def handler(inv: Invocation):
            seen_flags.append(inv.state.get("factory"))
            return next_handler(inv)

        return handler

    pipeline.set_invocation_factory(factory)
    pipeline.use(capture)

    def user():
        return "ok"

    wrapped = pipeline.build(user)
    assert wrapped() == "ok"
    assert created and created[0].state["factory"] == "custom"
    assert seen_flags == ["custom"]


def test_pipeline_injects_invocation_context_for_commands():
    pipeline = Pipeline()

    def seed_state(next_handler):
        def handler(inv: Invocation):
            inv.state["flag"] = "from-middleware"
            return next_handler(inv)

        return handler

    pipeline.use(seed_state)
    captured: dict[str, Any] = {}

    def command(ctx: InvocationContext, value: int):
        captured["type"] = type(ctx)
        captured["value"] = value
        captured["flag"] = ctx.state.get("flag")
        captured["name"] = ctx.name
        captured["args"] = ctx.args
        captured["kwargs"] = ctx.kwargs
        return ctx

    wrapped = pipeline.build(command, name="demo")
    sig = inspect.signature(wrapped)
    assert list(sig.parameters) == ["value"]

    ctx_obj = wrapped(5)
    assert isinstance(ctx_obj, InvocationContext)
    assert captured["type"] is InvocationContext
    assert captured["value"] == 5
    assert captured["flag"] == "from-middleware"
    assert captured["name"] == "demo"
    assert captured["args"] == (5,)
    assert captured["kwargs"] == {}


def test_pipeline_supports_command_context_alias():
    pipeline = Pipeline()
    seen: dict[str, Any] = {}

    def command(value: int, ctx: CommandContext):
        seen["is_instance"] = isinstance(ctx, CommandContext)
        seen["args"] = ctx.args
        return ctx.name

    wrapped = pipeline.build(command, name="alias")
    assert list(inspect.signature(wrapped).parameters) == ["value"]

    result = wrapped(10)
    assert result == "alias"
    assert seen["is_instance"] is True
    assert seen["args"] == (10,)


def test_pipeline_virtual_option_exposed_without_forwarding():
    pipeline = Pipeline()
    pipeline.add_virtual_option(
        "what_if",
        option=Option(False, "--what-if", help="Execute in what-if mode."),
    )

    observed: dict[str, Any] = {}

    def capture(next_handler):
        def handler(inv: Invocation):
            observed["kwargs"] = dict(inv.kwargs)
            observed["state"] = inv.state.get("virtual:what_if")
            return next_handler(inv)

        return handler

    pipeline.use(capture)

    def command(value: int):
        observed["value"] = value
        return value

    wrapped = pipeline.build(command)
    sig = inspect.signature(wrapped)
    assert "what_if" in sig.parameters

    result = wrapped(value=3, what_if=True)
    assert result == 3
    assert observed["value"] == 3
    assert observed["kwargs"]["what_if"] is True
    assert observed["state"] is True


def test_pipeline_extended_typer_command_receives_invocation_context():
    pipeline = Pipeline()

    def seed_state(next_handler):
        def handler(inv: Invocation):
            inv.state["flag"] = "from-middleware"
            return next_handler(inv)

        return handler

    pipeline.use(seed_state)
    app = ExtendedTyper(pipeline=pipeline)
    captured: dict[str, Any] = {}

    @app.command()
    def demo(ctx: InvocationContext, value: int):
        captured["type"] = type(ctx)
        captured["value"] = value
        captured["flag"] = ctx.state.get("flag")
        captured["name"] = ctx.name
        captured["args"] = ctx.args
        captured["kwargs"] = ctx.kwargs
        return "ok"

    command = app.registered_commands[0]
    sig = inspect.signature(command.callback)
    assert list(sig.parameters) == ["value"]

    runner = CliRunner()
    result = runner.invoke(app, ["5"])
    if result.exception:
        raise result.exception

    assert captured["type"] is InvocationContext
    assert captured["value"] == 5
    assert captured["flag"] == "from-middleware"
    assert captured["name"] == "demo"
    assert captured["args"] == ()
    assert captured["kwargs"] == {"value": 5}


def test_extended_typer_command_receives_invocation_context():
    app = ExtendedTyper()
    captured: dict[str, Any] = {}

    @app.command()
    def demo(ctx: InvocationContext, value: int):
        captured["type"] = type(ctx)
        captured["value"] = value
        captured["flag"] = ctx.state.get("flag")
        captured["name"] = ctx.name
        captured["args"] = ctx.args
        captured["kwargs"] = ctx.kwargs
        return "ok"

    command = app.registered_commands[0]
    sig = inspect.signature(command.callback)
    assert list(sig.parameters) == ["value"]

    runner = CliRunner()
    result = runner.invoke(app, ["5"])
    if result.exception:
        raise result.exception

    assert captured["type"] is InvocationContext
    assert captured["value"] == 5
    assert captured["name"] == "demo"
    assert captured["args"] == ()
    assert captured["kwargs"] == {"value": 5}

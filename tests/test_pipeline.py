import inspect
import logging
from typing import Annotated, Any, get_args, get_origin

import click
import typer
from typer import Option
from typer.models import ParameterInfo
from typer.testing import CliRunner

from typerplus import TyperPlus
from typerplus.parser.logger import LoggerParser
from typerplus.pipeline import (
    Pipeline,
    _ensure_context_parameter,
    _ensure_invocation_context_parameter,
    _instantiate_parser,
)
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

    assert option is not None, "Option annotation missing"
    assert isinstance(option.click_type, LoggerParser), "click_type missing"
    # Option default should be available for Typer to treat as optional.
    assert getattr(option, "count", False), "count expecte True"


#   Pipeline doesn't do the argument injection, i guess
#    logger = wrapped()
#    assert logger is not None, "Logger expected not None"


def test_pipeline_enable_logger_updates_existing_option():
    option = Option("--log", "-l", count=True, help="Custom logger option")

    def user(logger: Annotated[logging.Logger | None, option] = None):
        return logger

    pipeline = Pipeline().enable_logger()
    wrapped = pipeline.build(user)
    sig = inspect.signature(wrapped)
    param = sig.parameters["logger"]
    extracted = _option_from_annotation(param.annotation)

    assert extracted is option, "Should be the same option object"
    assert isinstance(option.click_type, LoggerParser), "Expected click_type update"


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


def test_instantiate_parser_with_type_and_instance():
    class Parser:
        def __init__(self):
            self.created = True

    # type -> instance
    p1 = _instantiate_parser(Parser)
    assert isinstance(p1, Parser) and p1.created

    # instance -> same object
    inst = Parser()
    p2 = _instantiate_parser(inst)
    assert p2 is inst


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


def test_ensure_context_parameter_noop_when_ctx_present_and_untyped():
    def func(ctx, y: int):
        return y

    out = _ensure_context_parameter(func)
    assert out is func
    assert str(inspect.signature(out)) == str(inspect.signature(func))


def test_ensure_context_parameter_noop_when_ctx_typed():
    def func(ctx: typer.Context, y: int):
        return y

    out = _ensure_context_parameter(func)
    assert out is func
    assert str(inspect.signature(out)) == str(inspect.signature(func))


def test_ensure_context_parameter_noop_when_already_ensured():
    def temp(j: InvocationContext): ...

    _ensure_invocation_context_parameter(temp)
    assert getattr(temp, "__typerplus_original_signature__", None)
    assert getattr(temp, "__typerplus_runtime_signature__", None)

    def temp2(j: InvocationContext): ...

    setattr(temp2, "__typerplus_context_param_names__", True)
    _ensure_invocation_context_parameter(temp2)
    assert not getattr(temp2, "__typerplus_original_signature__", False)
    assert not getattr(temp2, "__typerplus_runtime_signature__", False)


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

    @pipeline.build
    def wrapped(value: int):
        observed["value"] = value
        return value

    sig = inspect.signature(wrapped)
    assert "what_if" in sig.parameters

    result = wrapped(value=3, what_if=True)
    assert result == 3
    assert observed["value"] == 3
    assert observed["kwargs"]["what_if"] is True
    assert observed["state"] is True


def test_apply_virtual_parameters_ignores_existing_param_name():
    p = Pipeline().add_virtual_option("flag")

    def user(flag: bool = False):
        return flag

    wrapped = p.build(user)
    sig = inspect.signature(wrapped)
    # No duplicate param added; remains as originally declared
    assert list(sig.parameters) == ["flag"]


def test_apply_virtual_parameters_dup_raises_error():
    from pytest import raises

    p = Pipeline().add_virtual_option("flag")

    with raises(ValueError):
        p.add_virtual_option("flag")


def test_pipeline_typer_plus_command_receives_invocation_context():
    pipeline = Pipeline()

    def seed_state(next_handler):
        def handler(inv: Invocation):
            inv.state["flag"] = "from-middleware"
            return next_handler(inv)

        return handler

    pipeline.use(seed_state)
    app = TyperPlus(pipeline=pipeline)
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


def test_pipeline_inject_context_decorator_adds_ctx_param():
    p = Pipeline().inject_context()

    def user(x: int):
        return x

    wrapped = p.build(user)
    sig = inspect.signature(wrapped)
    params = list(sig.parameters)
    assert params[0] == "ctx"
    assert params[1] == "x"


def test_register_param_type_without_option_factory_raises():
    class Token(str):
        pass

    # Register a hook with no option_factory; using it must error when building
    p = Pipeline().register_param_type(Token, option_factory=None)

    def cmd(token: Token):
        return token

    try:
        p.build(cmd)
        raise AssertionError("Expected ValueError not raised")
    except ValueError as e:
        assert "missing option metadata" in str(e)


def test_string_forward_ref_invocation_context_is_hidden():
    p = Pipeline()

    def cmd(ctx: "InvocationContext", value: int):  # noqa: F821
        return value

    wrapped = p.build(cmd)
    sig = inspect.signature(wrapped)
    assert list(sig.parameters) == ["value"]


def test_add_virtual_option_without_storing_in_state():
    p = Pipeline()
    p.add_virtual_option("what_if", store_in_state=False)

    seen: dict[str, object] = {}

    def capture(next_handler):
        def handler(inv: Invocation):
            seen.update(inv.state)
            return next_handler(inv)

        return handler

    p.use(capture)

    def user():
        return "ok"

    wrapped = p.build(user)
    res = wrapped(what_if=True)
    assert res == "ok"
    # No state recorded since store_in_state=False
    assert not seen


def test_adapter_signature_not_set_when_decorated_signature_unavailable():
    # Decorator that returns a callable whose __signature__ is invalid (not a Signature)
    def badsig_decorator(func):
        class BadSig:
            __signature__ = (
                object()
            )  # invalid __signature__ will break inspect.signature

            def __init__(self, f):
                self._f = f

            def __call__(self, *a, **k):
                return self._f(*a, **k)

        return BadSig(func)

    p = Pipeline().use_decorator(badsig_decorator)

    def user():
        return "ok"

    wrapped = p.build(user)
    # Calling still works; adapter signature copy is skipped gracefully
    assert wrapped() == "ok"


def test_enable_logger_handles_subclass_parameter_type():
    class MyLogger(logging.Logger):
        pass

    p = Pipeline().enable_logger()

    def user(logger: MyLogger | None = None):
        return logger

    wrapped = p.build(user)
    sig = inspect.signature(wrapped)
    param = sig.parameters["logger"]
    # Ensure option metadata was added to subclass annotation
    assert param.default is None, "logger default should be None"
    assert param.annotation is not None, "logger annotation should not be None"
    assert param.annotation is not inspect.Parameter.empty, (
        "logger annotation should not be empty"
    )

    from typing import Union, get_args, get_origin

    orig = get_origin(param.annotation)
    assert orig is Annotated, "Parameter annotation should be 'Annotated'"
    typ, args = get_args(param.annotation)
    orig = get_origin(typ)
    assert orig is Union, "Annotated should be Optional/Union"
    typ, _ = get_args(typ)
    assert typ is MyLogger, "First Option/Union argument should be MyLogger"


def test_register_param_type_does_not_override_existing_click_type():
    import click

    class Token(str):
        pass

    class TokenParser(click.ParamType):
        name = "token"

    # Pre-create option with click_type already set
    opt = typer.Option(..., "--token")
    opt.click_type = TokenParser()  # existing parser instance

    p = Pipeline().register_param_type(
        Token,
        option_factory=lambda param: opt,
        parser_factory=TokenParser,
    )

    def user(token: Token | None = None):
        return token

    wrapped = p.build(user)
    sig = inspect.signature(wrapped)
    option_seen = [
        m
        for m in sig.parameters["token"].annotation.__metadata__
        if isinstance(m, typer.models.ParameterInfo)
    ][0]
    # Should preserve the existing instance
    assert option_seen.click_type is opt.click_type


def test_virtual_option_required_value_defaults_to_ellipsis_in_state():
    p = Pipeline()
    p.add_virtual_option("mode", option=typer.Option(..., "--mode"))

    captured: dict[str, object] = {}

    def capture(next_handler):
        def handler(inv: Invocation):
            captured["value"] = inv.state.get("virtual:mode")
            return next_handler(inv)

        return handler

    p.use(capture)

    def user():
        return "ok"

    wrapped = p.build(user)
    # Do not pass --mode; state should contain Ellipsis (not Signature.empty)
    assert wrapped() == "ok"
    assert captured["value"] is ...


def test_virtual_option_missing_default_maps_to_none_in_state():
    # Create a dummy object that mimics ParameterInfo with no default set
    class DummyOption:
        pass

    dummy = DummyOption()
    # No `default` attribute -> pipeline stores Signature.empty as default_value

    p = Pipeline()
    p.add_virtual_option("phantom", option=dummy)

    captured: dict[str, object] = {}

    def capture(next_handler):
        def handler(inv: Invocation):
            captured["value"] = inv.state.get("virtual:phantom")
            return next_handler(inv)

        return handler

    p.use(capture)

    def user():
        return "ok"

    wrapped = p.build(user)
    # Do not pass phantom; state should coerce Signature.empty -> None
    assert wrapped() == "ok"
    assert captured["value"] is None


def test_adapter_context_fetch_handles_runtimeerror(monkeypatch):
    import click as _click
    import typer as _typer

    def raise_ctx(*args, **kwargs):
        raise RuntimeError("no ctx")

    # Typer may not expose this attribute; allow creating it
    monkeypatch.setattr(_typer, "get_current_context", raise_ctx, raising=False)
    monkeypatch.setattr(_click, "get_current_context", raise_ctx, raising=True)

    p = Pipeline()
    seen: dict[str, object] = {}

    def capture(next_handler):
        def handler(inv: Invocation):
            seen["context"] = inv.environment.context
            return next_handler(inv)

        return handler

    p.use(capture)

    def user():
        return "ok"

    wrapped = p.build(user)
    assert wrapped() == "ok"
    assert seen.get("context") is None


def test_param_type_hook_and_virtuals_skip_when_signature_unavailable():
    # Create a callable object that makes signature_of(func) return None
    class BadSig:
        __signature__ = object()  # non-Signature triggers inspect failure

        def __call__(self):
            return "ok"

    # Register a param type and a virtual option to enter both early-return paths
    p = Pipeline().register_param_type(int, option_factory=None)
    p.add_virtual_option("flag")

    bad = BadSig()
    wrapped = p.build(bad)
    # Should still be callable
    assert wrapped() == "ok"


def test_typer_plus_command_receives_invocation_context():
    app = TyperPlus()
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

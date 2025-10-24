import inspect
from typing import Annotated, get_args, get_origin

import click
import typer
from typer.models import ParameterInfo

from typerplus.config import PipelineConfig
from typerplus.types import Invocation


def _option_from_annotation(annotation):
    if get_origin(annotation) is Annotated:
        _, *meta = get_args(annotation)
        for item in meta:
            if isinstance(item, ParameterInfo):
                return item
    return None


def test_pipeline_config_materialises_pipeline_with_components():
    decorator_calls: list[bool] = []
    middleware_states: list[str] = []
    factory_created: list[Invocation] = []

    def decorator(func):
        def template(verbose: bool = False): ...

        def wrapper(verbose: bool = False):
            decorator_calls.append(verbose)
            return func()

        wrapper.__signature__ = inspect.signature(template)
        return wrapper

    def middleware(next_handler):
        def handler(inv: Invocation):
            middleware_states.append(inv.state.get("factory", "missing"))
            return next_handler(inv)

        return handler

    def factory(
        *,
        original,
        target,
        state=None,
        environment,
        call,
    ) -> Invocation:
        inv = Invocation(
            original=original,
            target=target,
            environment=environment,
            call=call,
            state=state or {},
        )
        inv.state["factory"] = "custom"
        factory_created.append(inv)
        return inv

    def command():
        return "ok"

    config = (
        PipelineConfig()
        .add_decorator(decorator)
        .add_middleware(middleware)
        .set_invocation_factory(factory)
    )

    pipeline = config.to_pipeline()
    wrapped = pipeline.build(command)
    assert wrapped(verbose=True) == "ok"
    assert decorator_calls == [True]
    assert middleware_states == ["custom"]
    assert factory_created and factory_created[0].state["factory"] == "custom"


def test_pipeline_config_add_param_type_registers_option():
    class Token(str):
        pass

    class TokenParser(click.ParamType):
        name = "token"

        def convert(self, value, param, ctx):
            return Token(value.upper())

    config = PipelineConfig().add_param_type(
        Token,
        option_factory=lambda param: typer.Option(..., "--token"),
        parser_factory=TokenParser,
    )

    def command(token: Token | None = None):
        return token

    pipeline = config.to_pipeline()
    wrapped = pipeline.build(command)
    option = _option_from_annotation(
        inspect.signature(wrapped).parameters["token"].annotation
    )
    assert isinstance(option.click_type, TokenParser)
    assert option.click_type.convert("abc", None, None) == "ABC"


def test_pipeline_config_merge_allows_variant_clones():
    def mw(next_handler):
        def handler(inv: Invocation):
            inv.state["mw"] = inv.state.get("mw", 0) + 1
            return next_handler(inv)

        return handler

    base = PipelineConfig()
    variant_a = base.add_middleware(mw)
    variant_b = variant_a.add_param_type(
        int,
        option_factory=lambda param: typer.Option(..., "--count", type=int),
    )

    merged = base.merge(variant_b)
    assert merged.middlewares == variant_b.middlewares
    assert merged.param_type_hooks == variant_b.param_type_hooks


def test_pipeline_config_inject_context_adds_ctx_param():
    cfg = PipelineConfig().inject_context()
    pipeline = cfg.to_pipeline()

    def user(x: int):
        return x

    wrapped = pipeline.build(user)
    params = list(inspect.signature(wrapped).parameters)
    assert params[0] == "ctx"
    assert params[1] == "x"


def test_pipeline_config_virtual_option_applies():
    cfg = PipelineConfig().add_virtual_option(
        "what_if", option=typer.Option(False, "--what-if")
    )
    pipeline = cfg.to_pipeline()

    def user():
        return "ok"

    wrapped = pipeline.build(user)
    sig = inspect.signature(wrapped)
    assert "what_if" in sig.parameters


def test_add_decorators_and_middlewares_empty_return_self():
    cfg = PipelineConfig()
    assert cfg.add_decorators(()) is cfg
    assert cfg.add_middlewares(()) is cfg


def test_merge_invocation_factory_precedence_when_other_none():
    base = PipelineConfig().set_invocation_factory(None)
    other = PipelineConfig()  # also None
    merged = base.merge(other)
    # Remains None when other has None; preserves base
    assert merged.invocation_factory is None


def test_pipeline_config_add_decorators_appends_and_order():
    calls: list[str] = []

    def d1(func):
        def wrapper(*a, **k):
            calls.append("d1")
            return func(*a, **k)

        return wrapper

    def d2(func):
        def wrapper(*a, **k):
            calls.append("d2")
            return func(*a, **k)

        return wrapper

    base = PipelineConfig()
    cfg = base.add_decorators([d1, d2])
    assert cfg is not base
    assert cfg.decorators[-2:] == (d1, d2)

    pipeline = cfg.to_pipeline()

    def command():
        calls.append("body")
        return "ok"

    wrapped = pipeline.build(command)
    assert wrapped() == "ok"
    # Decorators wrap in registration order; last added runs outermost
    assert calls == ["d2", "d1", "body"]


def test_pipeline_config_add_middlewares_appends_and_execution_order():
    order: list[str] = []

    def mw_a(next):
        def handler(inv: Invocation):
            order.append("a_pre")
            r = next(inv)
            order.append("a_post")
            return r

        return handler

    def mw_b(next):
        def handler(inv: Invocation):
            order.append("b_pre")
            r = next(inv)
            order.append("b_post")
            return r

        return handler

    cfg = PipelineConfig().add_middlewares([mw_a, mw_b])
    pipeline = cfg.to_pipeline()

    def command():
        order.append("call")
        return "ok"

    wrapped = pipeline.build(command)
    assert wrapped() == "ok"
    assert order == ["a_pre", "b_pre", "call", "b_post", "a_post"]

import importlib
import inspect
import logging
from typing import Annotated, get_args, get_origin

import click
import pytest
import typer
from typer.models import ParameterInfo
from typer.testing import CliRunner

from testproj.poc import (
    ExtendedTyper,
    PipelineConfig,
    enable_logger,
    get_config,
    get_pipeline,
    register_param_type,
    setup,
    use_decorator,
    use_invocation_factory,
    use_middleware,
)
from testproj.poc.types import Invocation

poc_setup_module = importlib.import_module("testproj.poc.setup")

runner = CliRunner()


def test_setup_and_global_pipeline_basic():
    """Configure global pipeline; decorator exposes CLI option and middleware runs around command."""
    # Reset and configure global pipeline. Subsequent ExtendedTyper apps created
    # without an explicit pipeline will use this configured global pipeline.
    setup()

    events: list[str] = []

    def dec(func):
        # Registration-time signature decorator: Expose an option --x by
        # publishing a template signature; behavior forwards unchanged.
        def template(x: int = 0): ...

        def wrapper(*args, **kwargs):
            return func()

        wrapper.__signature__ = inspect.signature(template)
        return wrapper

    # Invoke-time middleware: records pre/post around the actual command call.
    def mw_a(next):
        def handler(inv):
            events.append("a_pre")
            try:
                return next(inv)
            finally:
                events.append("a_post")

        return handler

    use_decorator(dec)
    use_middleware(mw_a)

    # Build an app that implicitly uses the global pipeline configured above.
    app = ExtendedTyper()

    @app.command()
    def cmd():
        print("OK")

    # Option --x is recognized because the decorator modified the registered
    # command's signature at registration time.
    res = runner.invoke(app, ["--x", "3"])  # option recognized due to decorator
    if res.exception:
        raise res.exception

    assert res.exit_code == 0
    assert "OK" in res.stdout
    assert events == ["a_pre", "a_post"]


def test_setup_overwrites_global():
    """setup() resets the global pipeline so newly added middleware executes on fresh instance."""
    # Create a fresh pipeline replacing the prior one.
    setup()
    _ = get_pipeline()

    # Ensure adding another middleware works on the new instance
    events: list[str] = []

    # This middleware should run for apps created after the reset.
    def mw(next):
        def handler(inv):
            events.append("pre")
            r = next(inv)
            events.append("post")
            return r

        return handler

    use_middleware(mw)
    # New app uses the new global pipeline instance with our middleware.
    app = ExtendedTyper()

    @app.command()
    def cmd():
        print("X")

    res = runner.invoke(app)
    assert res.exit_code == 0
    assert events == ["pre", "post"]


def test_setup_enable_logger_global_pipeline():
    """Global enable_logger applies to subsequently created apps."""
    setup()
    enable_logger()

    captured: dict[str, int] = {}
    app = ExtendedTyper()

    @app.command()
    def cmd(logger: logging.Logger):
        captured["level"] = logger.level

    res = runner.invoke(app, ["-vv"])
    if res.exception:
        raise res.exception

    assert captured["level"] == logging.INFO


def _option_from_annotation(annotation):
    if get_origin(annotation) is Annotated:
        _, *meta = get_args(annotation)
        for item in meta:
            if isinstance(item, ParameterInfo):
                return item
    return None


def test_get_pipeline_creates_default_when_none():
    original = poc_setup_module._global_pipeline
    poc_setup_module._global_pipeline = None
    try:
        pipeline = get_pipeline()
        assert pipeline is poc_setup_module._global_pipeline
    finally:
        poc_setup_module._global_pipeline = original


def test_use_invocation_factory_sets_global_pipeline_factory():
    setup()
    captured_source: list[str] = []
    created: list[Invocation] = []

    def factory(
        *,
        app,
        original,
        target,
        args,
        kwargs,
        name=None,
        state=None,
    ) -> Invocation:
        inv = Invocation(
            app=app,
            original=original,
            target=target,
            args=args,
            kwargs=kwargs,
            name=name,
            state=state or {},
        )
        inv.state["source"] = "global_factory"
        created.append(inv)
        return inv

    use_invocation_factory(factory)

    pipeline = get_pipeline()

    def capture(next_handler):
        def handler(inv: Invocation):
            captured_source.append(inv.state.get("source"))
            return next_handler(inv)

        return handler

    pipeline.use(capture)

    def cmd():
        return "ok"

    try:
        wrapped = pipeline.build(cmd)
        assert wrapped() == "ok"
        assert created and created[0].state["source"] == "global_factory"
        assert captured_source == ["global_factory"]
        assert get_config().invocation_factory is factory
    finally:
        setup()


def test_setup_accepts_pipeline_config():
    setup()

    events: list[str] = []

    def mw(next_handler):
        def handler(inv: Invocation):
            events.append("mw")
            return next_handler(inv)

        return handler

    config = PipelineConfig().add_middleware(mw)

    try:
        setup(config=config)
        assert get_config() is config

        pipeline = get_pipeline()

        def cmd():
            return "ok"

        wrapped = pipeline.build(cmd)
        assert wrapped() == "ok"
        assert events == ["mw"]
    finally:
        setup()


def test_setup_with_config_and_args_raises():
    config = PipelineConfig()
    with pytest.raises(ValueError):
        setup(config=config, decorators=[lambda f: f])


def test_setup_register_param_type_delegates_to_global_pipeline():
    setup()

    class Token(str):
        pass

    class TokenParser(click.ParamType):
        name = "token"

        def convert(self, value, parameter, ctx):
            return Token(value.upper())

    register_param_type(
        Token,
        option_factory=lambda param: typer.Option(
            ..., "--token", help=f"{param.name} token"
        ),
        parser_factory=TokenParser,
    )

    pipeline = get_pipeline()

    def cmd(token: Token | None = None):
        return token

    try:
        wrapped = pipeline.build(cmd)
        param = inspect.signature(wrapped).parameters["token"]
        option = _option_from_annotation(param.annotation)
        assert option is not None
        assert isinstance(option.click_type, TokenParser)
    finally:
        setup()

import inspect
import logging
import sys
import typing
from logging import Logger
from typing import Annotated, Optional, Union

import typer
from pytest import raises
from rich.console import Console
from typer import Option

# from typer.models import TyperOption
from typer.testing import CliRunner

from testproj.annotation import TyperAnnotation
from testproj.parser.logger import LoggerParser

console = Console(file=sys.stderr)
runner = CliRunner()


def test_logger_annotation():
    option = Option()

    def _cmd(logger: Annotated[Logger, option] = None): ...

    sig = inspect.signature(_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)
    assert typer_ann.type is Logger
    assert typer_ann.annotated
    assert option in typer_ann.annotations


def test_logger_annotation_multiple():
    option = Option()
    sentinel = object()

    def _cmd(logger: Annotated[Logger, option, sentinel] = None): ...

    sig = inspect.signature(_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)
    assert typer_ann.type is Logger
    assert typer_ann.annotated
    assert option in typer_ann.annotations
    assert sentinel in typer_ann.annotations


def test_logger_annotation_optional():
    option = Option()
    sentinel = object()

    def _cmd(logger: Annotated[Optional[Logger], option, sentinel] = None): ...

    sig = inspect.signature(_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)
    assert typer_ann.type is Logger
    assert typer_ann.optional
    assert typer_ann.annotated
    assert option in typer_ann.annotations
    assert sentinel in typer_ann.annotations


def test_logger_annotation_union():
    option = Option()
    sentinel = object()

    def _cmd(logger: Annotated[Union[Logger, None], option, sentinel] = None): ...

    sig = inspect.signature(_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)
    assert typer_ann.type is Logger
    assert typer_ann.optional
    assert typer_ann.annotated
    assert option in typer_ann.annotations
    assert sentinel in typer_ann.annotations


def test_logger_annotation_or():
    option = Option()
    sentinel = object()

    def _cmd(logger: Annotated[Logger | None, option, sentinel] = None): ...

    sig = inspect.signature(_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)
    assert typer_ann.type is Logger
    assert typer_ann.optional
    assert typer_ann.annotated
    assert option in typer_ann.annotations
    assert sentinel in typer_ann.annotations


def test_logger_bare_annotation():
    def _cmd(logger: Logger = None): ...

    sig = inspect.signature(_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)
    assert typer_ann.type is Logger
    assert not typer_ann.annotated
    assert not typer_ann.optional


def test_logger_bare_optional():
    def _cmd(logger: Optional[Logger] = None): ...

    sig = inspect.signature(_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)
    assert typer_ann.type is Logger
    assert typer_ann.optional
    assert not typer_ann.annotated


def test_logger_bare_union():
    def _cmd(logger: Union[Logger, None] = None): ...

    sig = inspect.signature(_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)
    assert typer_ann.type is Logger
    assert typer_ann.optional
    assert not typer_ann.annotated


def test_logger_bare_or():
    def _cmd(logger: Logger | None = None): ...

    sig = inspect.signature(_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)
    assert typer_ann.type is Logger
    assert typer_ann.optional
    assert not typer_ann.annotated


def test_logger_int_annotation():
    def _cmd(logger: Logger | int = None): ...

    sig = inspect.signature(_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)
    assert all(map(lambda s: s in (Logger, int), typing.get_args(typer_ann.type)))
    assert not typer_ann.annotated
    assert not typer_ann.optional


def test_logger_int_optional():
    def _cmd(logger: Optional[Logger | int] = None): ...

    sig = inspect.signature(_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)
    # assert typer_ann.type is Logger
    assert all(map(lambda s: s in (Logger, int), typing.get_args(typer_ann.type)))
    assert typer_ann.optional
    assert not typer_ann.annotated


def test_logger_int_union():
    def _cmd(logger: Union[Logger, int, None] = None): ...

    sig = inspect.signature(_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)
    # assert typer_ann.type is Logger
    assert all(map(lambda s: s in (Logger, int), typing.get_args(typer_ann.type)))
    assert typer_ann.optional
    assert not typer_ann.annotated


def test_logger_int_or():
    def _cmd(logger: Logger | int | None = None): ...

    sig = inspect.signature(_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)
    # assert typer_ann.type is Logger
    assert all(map(lambda s: s in (Logger, int), typing.get_args(typer_ann.type)))
    assert typer_ann.optional
    assert not typer_ann.annotated


def test_logger_annotation_updates():
    app = typer.Typer()

    option = Option("--verbose", "-v", count=True)

    @app.command()
    def my_cmd(logger: Annotated[Logger | None, option] = None):
        assert logger is not None
        logger.critical("critical message")
        logger.error("error message")
        logger.warning("warning message")
        logger.info("info message")
        logger.debug("debug message")
        return

    with raises(RuntimeError):
        runner.invoke(app)

    sig = inspect.signature(my_cmd)

    param = sig.parameters["logger"]
    typer_ann = TyperAnnotation(param.annotation)

    count = 0
    for opt in typer_ann.find_parameter_info_arg():
        assert option is opt
        count += 1

    assert count == 1

    _logger = logging.getLogger(__name__)

    opt.click_type = LoggerParser()

    result = runner.invoke(app, "-vvv")
    if result.exception is not None:
        raise result.exception


def test_logger_parser_annotation_updates():
    """Can't use a ClickParam directly as a type"""
    app = typer.Typer()

    option = Option("--verbose", "-v", count=True)

    @app.command()
    def my_cmd(logger: Annotated[LoggerParser | None, option] = None):
        assert logger is not None
        return

    with raises(RuntimeError) as ex:
        runner.invoke(app, "-vvv")

    assert any(map(lambda s: "Type not yet supported:" in s, ex.value.args))

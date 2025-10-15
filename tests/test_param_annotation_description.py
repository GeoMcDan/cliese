import inspect
import typing
from logging import Logger
from typing import Annotated, Optional, Union

from typer import Option
from typer.testing import CliRunner

from testproj.annotation import TyperAnnotation

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

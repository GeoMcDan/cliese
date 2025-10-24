import logging
from logging import Logger
from typing import Annotated

import typer
from typer.testing import CliRunner

from typerplus.parser import LoggerParser

runner = CliRunner()


def test_logger_parser_handles_counted_option():
    app = typer.Typer()

    @app.command("counted")
    def counted(
        logger: Annotated[
            Logger,
            typer.Option("--verbose", "-v", click_type=LoggerParser(), count=True),
        ] = 0,
    ):
        assert logger.name == "counted"
        assert logger.level == logging.DEBUG
        logger.debug("counted verbosity")

    result = runner.invoke(app, ["-vv"])
    if result.exception:
        raise result.exception
    assert result.exit_code == 0


def test_logger_parser_accepts_string_levels():
    app = typer.Typer()

    @app.command("string-level")
    def string_level(
        logger: Annotated[
            Logger,
            typer.Option("--log-level", click_type=LoggerParser()),
        ] = "warning",
    ):
        assert logger.name == "string-level"
        assert logger.level == logging.ERROR
        logger.error("string level parsing")

    result = runner.invoke(app, ["--log-level", "error"])
    if result.exception:
        raise result.exception
    assert result.exit_code == 0


def test_logger_parser_rejects_unknown_level():
    app = typer.Typer()

    @app.command("bad-level")
    def bad_level(
        logger: Annotated[
            Logger,
            typer.Option("--log-level", click_type=LoggerParser()),
        ] = "warning",
    ):
        logger.warning("should not run")

    result = runner.invoke(app, ["--log-level", "super-loud"])
    assert result.exit_code != 0
    assert "unknown log level" in result.stderr.lower()


def test_logger_parser_accepts_logger_instance_default():
    app = typer.Typer()

    default_logger = logging.getLogger("preset")
    default_logger.setLevel(logging.DEBUG)

    @app.command("logger-default")
    def command(
        logger: Annotated[
            Logger,
            typer.Option("--log-level", click_type=LoggerParser()),
        ] = default_logger,
    ):
        # LoggerParser should accept a Logger default and use its level
        assert isinstance(logger, logging.Logger)
        assert logger.level == logging.DEBUG

    result = runner.invoke(app, [])
    if result.exception:
        raise result.exception
    assert result.exit_code == 0


def test_logger_parser_empty_string_rejected():
    app = typer.Typer()

    @app.command("empty-str")
    def empty_str(
        logger: Annotated[
            Logger,
            typer.Option("--log-level", click_type=LoggerParser()),
        ] = "warning",
    ):
        logger.warning("should not run")

    result = runner.invoke(app, ["--log-level", ""])  # empty string
    assert result.exit_code != 0
    assert "log level cannot be empty" in result.stderr.lower()


def test_logger_parser_numeric_string_high_value():
    app = typer.Typer()

    @app.command("num-high")
    def num_high(
        logger: Annotated[
            Logger,
            typer.Option("--log-level", click_type=LoggerParser()),
        ] = "20",
    ):
        assert logger.level == 20

    result = runner.invoke(app, [])
    if result.exception:
        raise result.exception
    assert result.exit_code == 0


def test_logger_parser_unsupported_value_type_and_count_edges():
    parser = LoggerParser()
    # Unsupported type (dict) raises ValueError in _coerce_level
    try:
        parser._coerce_level({})
        raise AssertionError("Expected ValueError not raised")
    except ValueError as e:
        assert "unsupported log level value" in str(e)

    # count <= 0 yields WARNING
    assert parser._coerce_level(0) == logging.WARNING
    # count == 1 yields INFO (using float input to cover float path)
    assert parser._coerce_level(1.0) == logging.INFO

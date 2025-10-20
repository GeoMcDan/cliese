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

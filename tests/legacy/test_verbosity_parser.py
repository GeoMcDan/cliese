import logging
from logging import Logger
from typing import Annotated

import typer
from typer.testing import CliRunner

from testproj.parser import VerbosityParser
from testproj.parser.logger import LoggerParser

runner = CliRunner()
_logger = logging.Logger(__name__)


def test():
    parser = VerbosityParser()
    logger = parser.parse(0)
    assert isinstance(logger, logging.Logger)
    assert logger.level == logging.NOTSET


def test_logger_command():
    app = typer.Typer()

    @app.command()
    def _cmd(
        logger: Annotated[
            Logger,
            typer.Option("--verbose", "-v", click_type=LoggerParser(), count=True),
        ] = 0,
    ):
        assert isinstance(logger, Logger)
        assert logger.level == logging.DEBUG
        _logger.debug("TOSETNOE")

    result = runner.invoke(app, "-vvv")

    if result.exception:
        raise result.exception

    assert result.exception is None
    assert result.exit_code == 0

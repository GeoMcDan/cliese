import logging
from logging import Logger
from typing import Annotated

import pytest
import typer
from typer import Context, Option
from typer.testing import CliRunner

from testproj import registration
from testproj.typer import ExtendedTyper

runner = CliRunner()
_logger = Logger(__name__)
_logger.setLevel(logging.DEBUG)

# ExtendedTyper.register_extension("logger", object)
registration.register_extension("logger", Logger)


def test_param_baseline():
    app = ExtendedTyper()

    @app.command()
    def func(verbose: Annotated[int, Option("--verbose", "-v", count=True)] = 0):
        return verbose

    result = runner.invoke(app, ["-vvv"])
    assert result.exit_code == 3

    result = runner.invoke(app, ["-v", "-v", "-v", "-v"])
    assert result.exit_code == 4

    result = runner.invoke(app, ["--verbose", "--verbose"])
    assert result.exit_code == 2


class ExtendedContext:
    def __init__(self):
        print("Creating ExtendedContext")


@pytest.fixture
def setup_logger_extension():
    with registration.registration_context() as ctx:
        yield ctx


def test_param_logger(setup_logger_extension):
    setup_logger_extension.register_extension("logger", Logger)

    app = ExtendedTyper()
    app.use_extension("logger")

    @app.command()
    def func(
        ctx: Context,
        logger: Annotated[Logger, Option("--verbose", "-v", count=True)] = None,
    ):
        obj = ctx.ensure_object(ExtendedContext)
        typer.echo(f"_Logger_: {obj}")
        _logger.debug(f"Logger: {logger}")
        return 0

    result = runner.invoke(app, ["-vvv"])
    assert result.exit_code == 3

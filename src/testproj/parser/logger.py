import logging
from typing import Callable

import click
from typer.core import TyperOption


class LoggerParser(click.ParamType):
    name = "Logger"

    def convert(self, value, parameter: TyperOption, ctx: click.Context):
        level = {
            0: logging.ERROR,
            1: logging.WARNING,
            2: logging.INFO,
            3: logging.DEBUG,
        }.get(value, logging.DEBUG)

        logger = logging.getLogger(ctx.command_path)
        logger.setLevel(level)
        return logger


class VerbosityParser:
    @staticmethod
    def default_factory(name: str, level: int | str):
        return logging.Logger(name=name, level=level)

    def __init__(self, factory: Callable[[int], logging.Logger] = default_factory):
        self.factory = factory

    def parse(self, verbosity: int):
        match verbosity:
            case 0:
                log_level = logging.NOTSET
            case 1:
                log_level = logging.CRITICAL
            case 2:
                log_level = logging.ERROR
            case 3:
                log_level = logging.WARN
            case 4:
                log_level = logging.INFO
            case _:
                log_level = logging.DEBUG

        if isinstance(self.factory, type) and issubclass(logging.Logger, self.factory):
            return logging.Logger(level=log_level)
        else:
            return self.factory("testing", log_level)

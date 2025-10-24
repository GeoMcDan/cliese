import logging
from typing import Any

import click

_logger = logging.getLogger(__name__)


class LoggerParser(click.ParamType):
    """Convert CLI verbosity/count or textual level into a configured logger."""

    name = "Logger"

    def convert(
        self,
        value: Any,
        parameter: click.Parameter | None,
        ctx: click.Context | None,
    ) -> logging.Logger:
        logger_name = (
            ctx.command_path if ctx and ctx.command_path else None
        ) or "typerplus"

        _logger.debug("value: %s, %s", value, type(value))
        try:
            level = self._coerce_level(value)
        except ValueError as exc:
            self.fail(str(exc), param=parameter, ctx=ctx)

        _logger.debug(
            "Value after coercion: %s, %s", level, logging.getLevelName(level)
        )
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        return logger

    def _coerce_level(self, value: Any) -> int:
        """Return a logging level derived from count or textual input."""

        if isinstance(value, logging.Logger):
            _logger.debug("Value already a logger")
            return value.level

        if isinstance(value, str):
            _logger.debug("Value is a string")
            stripped = value.strip()
            if not stripped:
                raise ValueError("log level cannot be empty")
            if stripped.isdigit():
                number = int(stripped)
                if number <= 4:
                    return self._level_from_count(number)
                return number
            upper = stripped.upper()

            nameToLevel = logging.getLevelNamesMapping()
            if upper in nameToLevel:
                return nameToLevel[upper]
            raise ValueError(f"unknown log level '{value}'")

        if isinstance(value, (int, float)):
            _logger.debug("Value is a number")
            count = int(value)
            return self._level_from_count(count)

        raise ValueError(f"unsupported log level value {value!r}")

    @staticmethod
    def _level_from_count(count: int) -> int:
        if count <= 0:
            return logging.ERROR
        if count == 1:
            return logging.WARNING
        if count == 2:
            return logging.INFO
        # Treat high verbosity counts as maximum detail
        return logging.DEBUG

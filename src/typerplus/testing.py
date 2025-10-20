from __future__ import annotations

from typer.testing import CliRunner

from .core import TyperPlus
from .pipeline import Pipeline

__all__ = ["TestApp", "runner"]

runner = CliRunner()


class TestApp:
    """Utility wrapper mirroring typer.testing ergonomics."""

    def __init__(self, *, pipeline: Pipeline | None = None):
        self.pipeline = pipeline or Pipeline()
        self.app = TyperPlus(pipeline=self.pipeline)
        self.runner = CliRunner()

    @property
    def command(self):
        return self.app.command

    def invoke(self, args=None, *, raise_ex: bool = True, **kwargs):
        """Invoke the CLI and optionally re-raise unexpected exceptions."""
        result = self.runner.invoke(self.app, args or [], **kwargs)
        if (
            raise_ex
            and result.exception
            and not isinstance(result.exception, SystemExit)
        ):
            raise result.exception
        return result

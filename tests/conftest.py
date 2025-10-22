import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def disable_color_output():
    """
    Disable ANSI color codes globally for Typer/Click during tests.
    """
    # Click and Typer both honor NO_COLOR if set.
    os.environ["NO_COLOR"] = "1"

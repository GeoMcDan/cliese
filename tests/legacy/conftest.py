import sys
from pathlib import Path

import pytest

import testproj.legacy.registration as registration

# Ensure 'src' is on sys.path when running tests without installing the package
_repo_root = Path(__file__).resolve().parents[2]
_src = _repo_root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


@pytest.fixture
def registration_context():
    with registration.registration_context() as ctx:
        yield ctx


# def _pytest_configure(config):
#    # Get pytest's configured log level (may be set via CLI or pytest.ini)
#    level_name = config.getoption("--log-cli-level") or config.getini("log_cli_level")
#    print("Level name:", level_name)
#    cli_format = config.getoption("--log-cli-format") or config.getini("log_cli_format")
#    print("CLI Format:", cli_format)
#    cli_date_format = config.getoption("--log-cli-date-format") or config.getini("log_cli_date_format")
#    print("CLI Date Format:", cli_date_format)
#    level = logging.getLevelName(level_name.upper())
#
#    # Remove any existing root handlers that pytest or another plugin attached
#    for handler in logging.root.handlers[:]:
#        logging.root.removeHandler(handler)
#
#    # Replace with RichHandler, respecting pytest configuration
#    logging.basicConfig(
#        level=level,
#        format=cli_format,
#        datefmt=cli_date_format,
#        handlers=[RichHandler(rich_tracebacks=True, markup=True)]
#    )

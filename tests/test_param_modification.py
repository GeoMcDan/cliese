from functools import wraps
from inspect import Parameter, Signature, signature
from logging import Logger, getLogger
from typing import Annotated

from typer import Option
from typer.testing import CliRunner

from testproj import registration
from testproj.typer import ExtendedTyper

runner = CliRunner()
_logger = getLogger(__name__)

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


def test_param_logger(setup_logger_extension):
    setup_logger_extension.register_extension("logger", Logger)

    app = ExtendedTyper()
    app.use_extension("logger")

    @app.command()
    def func(
        logger: Annotated[Logger, Option("--verbose", "-v", count=True)] = None,
    ):
        return 0

    # _logger.debug("Testing")
    result = runner.invoke(app, ["--verbose", 3])
    assert result.exit_code == 0


def test_change_signature():
    def _template(a: int) -> int:
        """template doc string"""
        ...

    def update_sig(template):
        def decorator2(func):
            def wrapper2(*args, **kwargs):
                "second decorator"
                return func(*args, **kwargs) + 3

            return wrapper2

        def decorator(func):
            @wraps(func)
            @decorator2
            def wrapper(*args, **kwargs):
                """taoseting"""
                return func(*args, **kwargs) + 1

            wrapper.__signature__ = signature(template)
            return wrapper

        return decorator

    def _temp(a):
        """a temp test function"""
        return a + 1

    # Test _temp signature
    sig = signature(_temp)
    assert str(sig) == "(a)"
    assert sig.parameters["a"].annotation is Parameter.empty
    assert sig.return_annotation is Signature.empty
    assert _temp.__doc__ == "a temp test function"
    assert _temp(3) == 4

    _temp_wrapped = update_sig(_template)(_temp)

    # Test _temp_wrapped signature
    sig = signature(_temp_wrapped)
    assert str(sig) == "(a: int) -> int"
    assert sig.parameters["a"].annotation is int
    assert sig.return_annotation is int
    assert _temp_wrapped.__doc__ == "a temp test function"
    assert _temp_wrapped(3) == 8

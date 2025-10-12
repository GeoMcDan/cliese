import logging

import pytest
from typer.testing import CliRunner

from testproj import registration
from testproj.typer import ExtendedTyper

runner = CliRunner()
logger = logging.getLogger(__name__)


def test_global_registration():
    def fake(): ...

    with registration.registration_context() as ctx:
        assert ExtendedTyper.get_registration_func() is None
        ctx.register(fake)
        assert ExtendedTyper.get_registration_func() is fake

    assert ExtendedTyper.get_registration_func() is None


def test_app_registration_init():
    def fake2(): ...

    app = ExtendedTyper(register=fake2)
    assert app.extension is fake2
    assert ExtendedTyper.get_registration_func() is None

    @app.command()
    def main_test(): ...


def test_app_registration_set():
    def fake3(): ...

    app = ExtendedTyper()
    app.register(fake3)

    assert app.extension is fake3
    assert ExtendedTyper.get_registration_func() is None


def test_command_extension():
    app = ExtendedTyper()
    ran = False

    def fake4(event: str, obj):
        nonlocal ran
        logging.info("%s: %s", event, obj)
        ran = True

    assert ran is False, "First test"

    @app.command("test-command", register=fake4)
    def cmd_test():
        return -1

    assert ran is False, "Second test"
    result = runner.invoke(app)

    # logger.debug("Result: %s", result)
    assert result.exit_code == -1
    assert ran is True


def test_command_decorator():
    app = ExtendedTyper()
    ran = False

    def fake4(func):
        def wrapper(*args, **kwargs):
            nonlocal ran
            ran = True
            result = func(*args, **kwargs)
            return result

        return wrapper

    assert ran is False, "First test"

    @app.command("test-command", register_decorator=fake4)
    def cmd_test():
        return -1

    assert ran is False, "Second test"
    result = runner.invoke(app)

    assert ran is True
    assert int(result.exit_code) == -1


def test_command_decorator_app_setter():
    def fake4(func):
        def wrapper(*args, **kwargs):
            nonlocal ran
            ran = True
            result = func(*args, **kwargs)
            return result

        return wrapper

    app = ExtendedTyper()
    app.register_decorator(fake4)
    ran = False

    assert ran is False, "First test"

    @app.command("test-command")
    def cmd_test():
        return -1

    assert ran is False, "Second test"
    result = runner.invoke(app)

    assert ran is True
    assert int(result.exit_code) == -1


def test_command_with_unsupported_type():
    app = ExtendedTyper()
    with registration.registration_context():

        @app.command()
        def cmd_test():
            return -1

        result = runner.invoke(app)
        assert result.exit_code == -1

    with registration.registration_context():

        @app.command()
        def cmd_test2(param: logging.Logger = None):
            return -1

        with pytest.raises(RuntimeError):
            result = runner.invoke(app)


def test_command_decorator_global_setter():
    def fake4(func):
        def wrapper(*args, **kwargs):
            nonlocal ran
            ran = True
            result = func(*args, **kwargs)
            return result

        return wrapper

    with registration.registration_context() as ctx:
        ctx.register_decorator(fake4)
        app = ExtendedTyper()
        ran = False

        assert ran is False, "First test"

        @app.command("test-command")
        def cmd_test():
            return -1

        assert ran is False, "Second test"
        result = runner.invoke(app)

        assert ran is True
        assert int(result.exit_code) == -1

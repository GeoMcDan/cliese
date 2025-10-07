from testproj import registration
from testproj.typer import ExtendedTyper


def test_global_registration():
    def fake(): ...

    with registration.register(fake):
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


def test_command_registration():
    from typer.testing import CliRunner

    runner = CliRunner()

    app = ExtendedTyper()

    ran = False

    def fake4():
        nonlocal ran
        ran = True

    assert ran is False, "First test"

    @app.command("test-command", register=fake4)
    def cmd_test():
        import typer

        raise typer.Exit(-1)

    assert ran is False, "Second test"
    result = runner.invoke(app)

    assert int(result.exit_code) == -1
    assert ran is True

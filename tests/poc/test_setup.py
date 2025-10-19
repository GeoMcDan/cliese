import inspect

from typer.testing import CliRunner

from testproj.poc import (
    ExtendedTyper,
    get_pipeline,
    setup,
    use_decorator,
    use_middleware,
)

runner = CliRunner()


def test_setup_and_global_pipeline_basic():
    """Configure global pipeline; decorator exposes CLI option and middleware runs around command."""
    # Reset and configure global pipeline. Subsequent ExtendedTyper apps created
    # without an explicit pipeline will use this configured global pipeline.
    setup()

    events: list[str] = []

    def dec(func):
        # Registration-time signature decorator: Expose an option --x by
        # publishing a template signature; behavior forwards unchanged.
        def template(x: int = 0): ...

        def wrapper(*args, **kwargs):
            return func()

        wrapper.__signature__ = inspect.signature(template)
        return wrapper

    # Invoke-time middleware: records pre/post around the actual command call.
    def mw_a(next):
        def handler(inv):
            events.append("a_pre")
            try:
                return next(inv)
            finally:
                events.append("a_post")

        return handler

    use_decorator(dec)
    use_middleware(mw_a)

    # Build an app that implicitly uses the global pipeline configured above.
    app = ExtendedTyper()

    @app.command()
    def cmd():
        print("OK")

    # Option --x is recognized because the decorator modified the registered
    # command's signature at registration time.
    res = runner.invoke(app, ["--x", "3"])  # option recognized due to decorator
    if res.exception:
        raise res.exception

    assert res.exit_code == 0
    assert "OK" in res.stdout
    assert events == ["a_pre", "a_post"]


def test_setup_overwrites_global():
    """setup() resets the global pipeline so newly added middleware executes on fresh instance."""
    # Create a fresh pipeline replacing the prior one.
    setup()
    _ = get_pipeline()

    # Ensure adding another middleware works on the new instance
    events: list[str] = []

    # This middleware should run for apps created after the reset.
    def mw(next):
        def handler(inv):
            events.append("pre")
            r = next(inv)
            events.append("post")
            return r

        return handler

    use_middleware(mw)
    # New app uses the new global pipeline instance with our middleware.
    app = ExtendedTyper()

    @app.command()
    def cmd():
        print("X")

    res = runner.invoke(app)
    assert res.exit_code == 0
    assert events == ["pre", "post"]

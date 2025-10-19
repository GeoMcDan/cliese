import inspect

from typer.testing import CliRunner

from testproj.poc import ExtendedTyper, Pipeline

runner = CliRunner()


def test_extended_typer_uses_pipeline_decorator_and_middleware():
    """ExtendedTyper uses pipeline: decorator exposes option and middleware wraps execution."""
    events: list[str] = []

    def dec(func):
        # Registration-time: publish a signature that adds --x while
        # forwarding the call unchanged. Printing x here makes the effect
        # observable in stdout for the assertion below.
        def template(x: int = 0): ...

        def wrapper(*args, **kwargs):
            print(kwargs.get("x", 0))
            return func()

        wrapper.__signature__ = inspect.signature(template)
        return wrapper

    # Invoke-time: simple pre/post wrapper to show middleware ordering works
    # with ExtendedTyper in the same way as with bare Pipeline.
    def mw(next):
        def handler(inv):
            events.append("pre")
            r = next(inv)
            events.append("post")
            return r

        return handler

    # Compose decorator + middleware and pass explicitly to the app. If no
    # pipeline is provided, ExtendedTyper would use the global one.
    pipeline = Pipeline().use_decorator(dec).use(mw)
    app = ExtendedTyper(pipeline=pipeline)

    @app.command()
    def hello():
        print("HELLO")

    # Typer sees --x from the decorator-altered signature; mw wraps around the
    # call, recording events, while the decorated function prints the value.
    res = runner.invoke(app, ["--x", "7"])
    if res.exception:
        raise res.exception

    # stdout prints x first (from decorator), then the body; middleware ran.
    assert "7" in res.stdout
    assert "HELLO" in res.stdout
    assert events == ["pre", "post"]

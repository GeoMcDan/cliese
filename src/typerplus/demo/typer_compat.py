from typer import Context, echo

from typerplus import TyperPlus

app = TyperPlus(no_args_is_help=True)


@app.command()
def hello(name: str):
    echo(f"Hello, {name}")


@app.command()
def howdy(ctx: Context, name: str):
    echo(f"Howdy, {name}")
    echo(repr(ctx))

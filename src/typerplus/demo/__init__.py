from typer import echo

from typerplus import TyperPlus

app = TyperPlus()


@app.command()
def hello(name: str):
    echo(f"Hello, {name}")

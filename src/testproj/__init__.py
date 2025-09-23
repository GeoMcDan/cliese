import typer

main = typer.Typer(add_completion=False, no_args_is_help=True)

@main.command()
def hello():
    print("Hello from testproj!")

@main.command()
def test():
    print("This is a test")

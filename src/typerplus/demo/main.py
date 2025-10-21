from typer import Typer

from typerplus.demo.typer_compat import app as compat_app

app = Typer()

app.add_typer(compat_app, name="compat")

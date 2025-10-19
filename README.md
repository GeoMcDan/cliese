# Try-Visitor

**The next evolution of Typer-style CLIs.** Try-Visitor keeps the ergonomics of `typer.Typer` while layering a composable pipeline that feels closer to FastAPI or modern web frameworks. Registration-time decorators and invoke-time middleware live side by side, letting you shape signatures, inject dependencies, and orchestrate cross-cutting concerns without contorting your command functions.

- ⚙️ **Design intent:** treat command execution like an HTTP request—run it through a predictable pipeline that can observe and mutate state.
- 🧩 **Composability first:** decorators amend the public signature Typer inspects; middleware wraps the actual invocation, observing shared state and Typer’s runtime context.
- 🧠 **Context aware:** expose Typer/Click context, args/kwargs, and shared state through a single `Invocation` object so middlewares stay clean and testable.

> _“FastAPI is to Typer what Typer is to Click.”_ Try-Visitor aims to push that analogy one step further.

### Acknowledgements

- **bottor** — for the foundational ideas around middleware-style CLI composition.
- **Sebastián Ramírez (tiangolo)** — creator of Typer & FastAPI; this project stands on his shoulders.

---

## Quick Start: Drop-in Typer Feel

```python
from testproj import ExtendedTyper as Typer

app = Typer()

@app.command()
def hello(name: str = "World"):
    print(f"Hello, {name}!")

if __name__ == "__main__":
    app()
```

`ExtendedTyper` mirrors the default Typer API, so you can alias it and ship existing commands unchanged. The real power appears when you start composing the pipeline.

---

## Pipelines, Decorators, and Middleware

```python
from testproj import ExtendedTyper, Pipeline
from testproj.types import Invocation

def echo_signature(func):
    """Registration-time decorator: expose a --times option without touching the body."""
    import inspect

    def template(times: int = 1): ...

    def wrapper(*args, **kwargs):
        return func(times=kwargs.get("times", 1))

    wrapper.__signature__ = inspect.signature(template)
    return wrapper

def log_invocation(next_handler):
    """Invoke-time middleware: log before and after the command runs."""
    def handler(inv: Invocation):
        inv.state["events"] = inv.state.get("events", [])
        inv.state["events"].append("pre")
        result = next_handler(inv)
        inv.state["events"].append("post")
        return result
    return handler

pipeline = Pipeline().use_decorator(echo_signature).use(log_invocation)
app = ExtendedTyper(pipeline=pipeline)

@app.command()
def greet(times: int):
    for _ in range(times):
        print("Hey there!")
```

- **Decorators** rewrite the signature Typer inspects (`--times` above) without mutating the original function.
- **Middleware** receives an `Invocation` object with the Typer app, command name, args/kwargs, and shared `state` dict.

---

## Logger Injection with Verbosity Counting

```python
from testproj import ExtendedTyper
import logging

app = ExtendedTyper()
app.enable_logger()  # Adds -v / --verbose (counting) and a Logger parser.

@app.command()
def status(logger: logging.Logger):
    logger.info("Informational message")
    logger.debug("Debug noise")
```

Run it:

```bash
$ app status
# default level (WARNING) prints nothing

$ app status -v
# now INFO messages appear

$ app status -vv
# LoggerParser bumps level to DEBUG
```

The built-in parser mirrors the behavior tested in `tests/poc/test_pipeline.py` and `tests/poc/test_typer_ext.py`, using `count=True` to map repeat flags into logger levels.

---

## Custom Types & Option Metadata

```python
import click
import typer
from testproj import ExtendedTyper

class AccessToken(str):
    ...

class AccessTokenParser(click.ParamType):
    name = "token"

    def convert(self, value, param, ctx):
        if not value.startswith("tok_"):
            self.fail("Tokens must start with 'tok_'", param, ctx)
        return AccessToken(value)

app = ExtendedTyper()
app.register_param_type(
    AccessToken,
    option_factory=lambda param: typer.Option(..., "--token", "-t", help="API token"),
    parser_factory=AccessTokenParser,
)

@app.command()
def fetch(token: AccessToken):
    print(f"Using {token!r}")
```

`register_param_type` wires a parser plus option metadata, reusing the same hooks the tests exercise.

---

## Middleware & Context Access

```python
from testproj import ExtendedTyper
from testproj.types import Invocation

app = ExtendedTyper()
app.inject_context()  # ensure Typer Context is injected into commands

@app.before_invoke
def capture_context(inv: Invocation):
    ctx = inv.context  # click/typer context
    inv.state["command_path"] = ctx.command_path if ctx else None

@app.command()
def build(ctx):
    assert ctx is inv.context  # same object surfaced to the handler
    print("Command path:", ctx.command_path)
```

- `inject_context` prepends a `ctx: typer.Context` parameter to commands that don’t already specify one.
- Middlewares (and handlers) access the context via `inv.context` without rewiring every function signature manually.

---

## Global Pipeline Configuration

Prefer central configuration? Use the global helpers:

```python
from testproj import (
    ExtendedTyper,
    enable_logger,
    inject_context,
    use_middleware,
)
from testproj.types import Invocation

def trace(next_handler):
    def handler(inv: Invocation):
        print(f"→ {inv.name}")
        return next_handler(inv)
    return handler

inject_context()
enable_logger()
use_middleware(trace)

app = ExtendedTyper()  # picks up the configured global pipeline
```

Any `ExtendedTyper` created after the configuration call inherits the shared decorators, middleware, and invocation factory.

---

## What’s Next

- richer context coercion helpers (Typer vs. Click contexts)
- plug-and-play middleware catalog for logging, telemetry, retries
- deeper integration tests and docs as the ecosystem grows

Feedback and contributions are welcome—this README will expand as new capabilities land. Until then, enjoy the upgraded Typer experience!

# Typer Plus

**Pipeline-powered CLIs without giving up Typer’s ergonomics.** Typer Plus (Try-Visitor) layers a FastAPI-style middleware pipeline on top of `typer.Typer` so you can shape signatures, inject dependencies, and coordinate cross-cutting behaviour while keeping command functions clean.

## Feature Highlights

- **Composable pipeline:** registration-time decorators and invoke-time middleware run for every command, just like HTTP middleware.
- **Signature transforms:** publish CLI options without touching the handler—ideal for toggles, feature flags, or shared options.
- **Invocation insight:** a single `Invocation` object exposes the Typer/Click context, args, kwargs, and shared state.
- **Custom type injection:** register your own parsers (e.g. API tokens) or rely on the built-in logger integration.
- **Virtual options:** surface pipeline-owned options (such as `--what-if`) to Typer while keeping handlers unaware; middleware reads the values from invocation state.
- **Flexible configuration:** use a dedicated `Pipeline`, global helpers via `typerplus.setup`, or a mix of both.
- **100% Typer compatible:** `ExtendedTyper` is a drop-in replacement; an empty pipeline behaves exactly like Typer.

> _“FastAPI is to Typer what Typer is to Click.”_ Typer Plus finishes the analogy by giving Typer a first-class middleware story.

---

## Quick Start

```python
from typerplus import ExtendedTyper as Typer

app = Typer()

@app.command()
def hello(name: str = "World"):
    print(f"Hello, {name}!")

if __name__ == "__main__":
    app()
```

Alias `ExtendedTyper` and keep exporting commands. Until you add pipeline features, behaviour is identical to Typer.

---

## Core Concepts

### Pipeline, Decorators, Middleware

```python
import inspect
from typerplus import ExtendedTyper, Pipeline
from typerplus.types import Invocation

def add_times_option(func):
    def template(times: int = 1): ...

    def wrapper(*args, **kwargs):
        return func(times=kwargs.get("times", 1))

    wrapper.__signature__ = inspect.signature(template)
    return wrapper

def trace(next_handler):
    def handler(inv: Invocation):
        inv.state.setdefault("events", []).append("pre")
        result = next_handler(inv)
        inv.state["events"].append("post")
        return result
    return handler

pipeline = Pipeline().use_decorator(add_times_option).use(trace)
app = ExtendedTyper(pipeline=pipeline)

@app.command()
def greet(times: int):
    for _ in range(times):
        print("Hey there!")
```

- **Decorators** run at registration time and only affect the signature Typer inspects.
- **Middleware** runs at invocation time with an `Invocation` object that exposes app, command name, args/kwargs, shared state, and Click/Typer context.

### Invocation & Context Access

```python
from typerplus import ExtendedTyper
from typerplus.types import Invocation

app = ExtendedTyper()
app.inject_context()  # ensures handlers can accept ctx: typer.Context

@app.before_invoke
def capture(inv: Invocation):
    inv.state["command_path"] = inv.context.command_path if inv.context else None

@app.command()
def build(ctx):
    print("Command path:", ctx.command_path)
```

`inject_context` prepends a `ctx` parameter when missing. Middleware and handlers can also use `inv.command_context` to interact with the same data via an ergonomic façade.

---

## Custom Type Injection

```python
import click
import typer
from typerplus import ExtendedTyper

class AccessToken(str): ...

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

`register_param_type` adjusts the signature Typer sees and wires the converter Click expects—no manual option definitions required.

---

## Logger Integration

```python
import logging
from typerplus import ExtendedTyper

app = ExtendedTyper()
app.enable_logger()  # exposes -v/--verbose and returns a configured logging.Logger

@app.command()
def status(logger: logging.Logger):
    logger.info("Informational message")
    logger.debug("Debug trace")
```

- `LoggerParser` converts count-based verbosity (`-vv`) **and** textual levels (`--log-level debug`).
- Loggers are named after `ctx.command_path`, keeping log output grouped by command.

---

## Virtual Options

Virtual options let the pipeline surface CLI switches without forwarding them to handlers. They are ideal for middleware-driven behaviour such as dry-run or preview modes.

```python
from typerplus import ExtendedTyper
from typerplus.types import Invocation

app = ExtendedTyper()
app.add_virtual_option("what_if")  # exposes --what-if to Typer

@app.use  # shorthand for pipeline.use(middleware)
def capture_what_if(next_handler):
    def handler(inv: Invocation):
        flag = inv.state.get("virtual:what_if", False)
        if flag:
            print("Running in what-if mode")
        return next_handler(inv)
    return handler

@app.command()
def deploy(environment: str):
    print(f"Deploying to {environment}")
```

- Typer advertises `--what-if` in `--help` and parses it normally.
- The runtime pipeline removes `what_if` from handler kwargs and stores the value in `inv.state["virtual:what_if"]` so middleware can react.

---

## Configuration & Setup Options

Prefer central configuration? Compose once, reuse everywhere:

```python
from typerplus import (
    ExtendedTyper,
    enable_logger,
    inject_context,
    add_virtual_option,
    use_middleware,
)
from typerplus.types import Invocation

def audit(next_handler):
    def handler(inv: Invocation):
        print(f"-> {inv.name}")
        return next_handler(inv)
    return handler

inject_context()
enable_logger()
add_virtual_option("what_if")
use_middleware(audit)

app = ExtendedTyper()  # picks up the configured pipeline
```

Behind the scenes a `PipelineConfig` tracks decorators, middleware, param types, virtual options, and invocation factories. You can clone or merge configurations, or create bespoke `Pipeline` instances for each app.

---

## Typer Compatibility

- `ExtendedTyper` mirrors `typer.Typer` methods (`command`, `callback`, `before_invoke`, `after_invoke`, etc.).
- A fresh `Pipeline()` (or the global default) with no additions behaves exactly like Typer.
- Existing Typer applications can migrate incrementally: alias `ExtendedTyper`, then opt into pipeline features as needed.

---

## Acknowledgements

- **bottor** – foundational exploration of middleware-style CLI composition.
- **Sebastián Ramírez (tiangolo)** – creator of Typer & FastAPI; this project builds on his ecosystem.

---

Pull requests, middleware examples, and docs improvements are welcome. Enjoy the upgraded Typer experience!

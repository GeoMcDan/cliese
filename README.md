# Typer Plus

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
![codecov](https://img.shields.io/codecov/c/github/geomcdan/cliese/main)
![license](https://img.shields.io/github/license/geomcdan/cliese)
![latest tag](https://img.shields.io/github/v/tag/geomcdan/cliese)
![checks](https://img.shields.io/github/check-runs/geomcdan/cliese/main)
![last commit](https://img.shields.io/github/last-commit/geomcdan/cliese)
![commits](https://badgen.net/github/commits/geomcdan/cliese)
![prs](https://badgen.net/github/closed-prs/geomcdan/cliese)
![version](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FGeoMcDan%2Fcliese%2Frefs%2Fheads%2Fmain%2Fpyproject.toml)
![commitactivity](https://img.shields.io/github/commit-activity/m/geomcdan/cliese)


**Pipeline-powered CLIs without giving up Typer's ergonomics.** Typer Plus layers a middleware pipeline on top of `typer.Typer` so you can shape signatures, inject dependencies, and coordinate cross-cutting behavior while keeping command functions clean.

## Feature Highlights

- **Composable pipeline:** registration-time decorators and invoke-time middleware run for every command, mirroring HTTP middleware.
- **Signature transforms:** publish CLI options without editing the command function for feature flags or shared behaviors provided by middleware.
- **Custom type injection:** register parsers and option metadata for your domain-specific types.
- **Logger integration:** supply a logger whose level is driven by counted verbosity flags or textual log-level arguments.
- **Virtual options:** expose pipeline-owned switches (for example `--what-if`) while keeping the command function unaware and letting middleware react.
- **Flexible configuration:** assemble pipelines ad hoc or configure them globally through `typerplus.setup`.
- **Typer compatibility:** an empty pipeline behaves exactly like Typer, so `TyperPlus` can stand in for `typer.Typer` while you iterate.

## Quick Start

```python
from typerplus import TyperPlus

app = TyperPlus()

@app.command()
def hello(name: str = "World"):
    print(f"Hello, {name}!")

if __name__ == "__main__":
    app()
```

Alias `TyperPlus` and keep exporting commands. Until you add pipeline features, behavior is identical to Typer.

## Core Concepts

### Pipeline, Decorators, Middleware

```python
import inspect
from typerplus import TyperPlus, Pipeline
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
app = TyperPlus(pipeline=pipeline)

@app.command()
def greet(times: int):
    for _ in range(times):
        print("Hey there!")
```

- **Decorators** run at registration time and only affect the signature Typer inspects.
- **Middleware** runs at invocation time with an `Invocation` object that exposes app, command name, args/kwargs, shared state, and Click/Typer context.

### Invocation & Context Access

```python
from typerplus import TyperPlus
from typerplus.types import Invocation

app = TyperPlus()
app.inject_context()  # ensures handlers can accept ctx: typer.Context

@app.before_invoke
def capture(inv: Invocation):
    inv.state["command_path"] = inv.context.command_path if inv.context else None

@app.command()
def build(ctx):
    print("Command path:", ctx.command_path)
```

`inject_context` prepends a `ctx` parameter when missing. Middleware and handlers can also use `inv.command_context` to interact with the same data via an ergonomic facade.

## Custom Type Injection

```python
import click
import typer
from typerplus import TyperPlus

class AccessToken(str): ...

class AccessTokenParser(click.ParamType):
    name = "token"

    def convert(self, value, param, ctx):
        if not value.startswith("tok_"):
            self.fail("Tokens must start with 'tok_'", param, ctx)
        return AccessToken(value)

app = TyperPlus()
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

## Logger Integration

```python
import logging
from typerplus import TyperPlus

app = TyperPlus()
app.enable_logger()  # exposes -v/--verbose and returns a configured logging.Logger

@app.command()
def status(logger: logging.Logger):
    logger.info("Informational message")
    logger.debug("Debug trace")
```

- `LoggerParser` converts count-based verbosity (`-vv`) **and** textual levels (`--log-level debug`).
- Loggers are named after `ctx.command_path`, keeping log output grouped by command.

## Virtual Options

Virtual options let the pipeline surface CLI switches without forwarding them to handlers. They are ideal for middleware-driven behavior such as dry-run or preview modes.

```python
from typerplus import TyperPlus
from typerplus.types import Invocation

app = TyperPlus()
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

## Configuration & Setup Options

Prefer central configuration? Compose once, reuse everywhere:

```python
from typerplus import (
    TyperPlus,
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

app = TyperPlus()  # picks up the configured pipeline
```

Behind the scenes a `PipelineConfig` tracks decorators, middleware, param types, virtual options, and invocation factories. You can clone or merge configurations, or create bespoke `Pipeline` instances for each app.

## Typer Compatibility

Not a drop-in replacement, but an extension. TyperPlus directly extends the Typer class.

- `TyperPlus` mirrors `typer.Typer` methods (`command`, `callback`, `before_invoke`, `after_invoke`, etc.).
- A fresh `Pipeline()` (or the global default) with no additions behaves exactly like Typer.
- Existing Typer applications can migrate incrementally: alias `TyperPlus`, then opt into pipeline features as needed.

## Disclaimer

This project is a proof of concept, not a production-ready framework. It gathers together experiments, personal helpers, and quick hacks I have repeated across several Typer projects. I paused feature work to document the ideas, wrap them in a test harness, and share the direction publicly.

The design is evolving. Concepts borrowed from OWIN and ASP.NET Core but the AI coding assistant undoubtedly pulling from well-known, tried and true concepts from from FastAPI and Flask. I frequently relied on an AI coding assistant while sketching components. The intent is to show what a richer CLI pipeline could feel like. I'm working toward a stable release.

## Acknowledgements

- **Sebastian Ramirez (tiangolo)** – creator of Typer & FastAPI; this project builds on his ecosystem.




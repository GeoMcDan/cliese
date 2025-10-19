from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, Iterable

from .types import CommandHandler, Decorator, Invocation, Middleware, ensure_signature


class Pipeline:
    """
    A Pythonic command middleware pipeline.

    - Decorators affect the function signature Typer inspects.
    - Middlewares wrap invoke-time behavior (pre/post) around the final call.

    Usage:
        p = Pipeline()
        p.use_decorator(my_sig_transform)
        p.use(my_invoke_middleware)
        wrapped = p.build(user_func, app=my_typer)
    """

    def __init__(
        self,
        *,
        decorators: Iterable[Decorator] | None = None,
        middlewares: Iterable[Middleware] | None = None,
    ):
        self._decorators: list[Decorator] = list(decorators or [])
        self._middlewares: list[Middleware] = list(middlewares or [])

    # Registration
    def use(self, middleware: Middleware) -> "Pipeline":
        self._middlewares.append(middleware)
        return self

    def use_decorator(self, decorator: Decorator) -> "Pipeline":
        self._decorators.append(decorator)
        return self

    # Building
    def build(
        self, func: Callable[..., Any], *, app: Any = None, name: str | None = None
    ) -> Callable[..., Any]:
        """Return a callable to register with Typer.

        The returned function:
          - has the signature produced by applied decorators
          - runs the invoke middleware chain around the call
        """

        original = func

        # Apply signature/metadata decorators in registration order (outermost first)
        decorated = func
        for dec in self._decorators:
            decorated = dec(decorated)

        # Ensure Typer can read the final signature
        ensure_signature(decorated)

        # Base handler makes the actual call
        def base(inv: Invocation) -> Any:
            return inv.target(*inv.args, **inv.kwargs)

        # Compose invoke middlewares (last registered runs innermost)
        handler: CommandHandler = base
        for mw in reversed(self._middlewares):
            handler = mw(handler)

        # Adapter registered with Typer; signature must match `decorated`
        @wraps(decorated)
        def adapter(*args: Any, **kwargs: Any) -> Any:
            inv = Invocation(
                app=app,
                original=original,
                target=decorated,
                args=args,
                kwargs=kwargs,
                name=name,
            )
            return handler(inv)

        # Guarantee Typer sees the signature from `decorated` even with wraps
        try:
            adapter.__signature__ = inspect.signature(decorated)
        except (TypeError, ValueError):
            pass

        return adapter

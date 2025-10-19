import inspect

from testproj.poc import Pipeline


def test_pipeline_decorator_affects_signature():
    """Pipeline decorator updates the wrapped function's signature via __signature__."""

    # "user" represents the developer's original command function. It has no
    # parameters; the pipeline should be able to expose additional CLI options
    # by changing the visible signature Typer inspects at registration time,
    # without changing the function body or behavior.
    def user():
        return "ok"

    def dec(func):
        # Registration-time decorator: it adjusts only how the function LOOKS
        # (its signature), not what it does. Typer will reflect this signature
        # and expose a corresponding option (--x) on the CLI.
        def template(x: int = 0): ...

        # Forwarding wrapper; for this test we ignore provided args/kwargs and
        # just call the original function to prove behavior is unchanged.
        def wrapper(*args, **kwargs):
            return func()

        # Publish the template's signature so reflection shows "(x: int = 0)".
        wrapper.__signature__ = inspect.signature(template)
        return wrapper

    p = Pipeline().use_decorator(dec)

    # build() constructs an adapter Typer will register:
    #  - applies the decorator to get a "decorated" target with the new
    #    signature
    #  - returns an adapter whose __signature__ mirrors the decorated target
    #    so Typer sees the added "x: int = 0" parameter
    wrapped = p.build(user)

    # The adapter should advertise the decorated signature exactly.
    sig = inspect.signature(wrapped)
    assert str(sig) == "(x: int = 0)"
    assert wrapped() == "ok"


def test_pipeline_middleware_order_and_state():
    """Middleware executes in order and shares/updates state around the user call."""
    order: list[str] = []

    # Middleware A runs first (outermost). It records pre/post markers and
    # seeds state so inner middleware(s) can read/extend it.
    def mw_a(next):
        def handler(inv):
            order.append("a_pre")
            inv.state["a"] = 1
            r = next(inv)
            order.append("a_post")
            return r

        return handler

    # Middleware B runs second (inner), sees state from A, and appends to it.
    def mw_b(next):
        def handler(inv):
            order.append("b_pre")
            inv.state["b"] = inv.state.get("a", 0) + 1
            r = next(inv)
            order.append("b_post")
            return r

        return handler

    # The developer's original command function. The middlewares wrap around
    # this call, producing the expected pre/call/post order.
    def user():
        order.append("call")
        return "ok"

    # Register A then B: A is outer, B is inner. build() composes the chain
    # so that invocation order is A.pre -> B.pre -> user -> B.post -> A.post.
    p = Pipeline().use(mw_a).use(mw_b)
    wrapped = p.build(user)
    result = wrapped()
    assert result == "ok"
    assert order == ["a_pre", "b_pre", "call", "b_post", "a_post"]

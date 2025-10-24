import inspect

from typerplus import Invocation
from typerplus.types import (
    InvocationCall,
    InvocationContext,
    InvocationEnvironment,
)


def test_invocation_dataclass_fields_and_state():
    """Validate Invocation fields pass through and its mutable state dict persists values."""
    # Invocation is the context object the pipeline passes through middlewares
    # and into the base handler. It carries metadata and a shared, mutable
    # state dict that middlewares can read/write.
    environment = InvocationEnvironment(app=None, name="cmd", context=None)
    call = InvocationCall(args=(1, 2), kwargs={"a": 3})
    inv = Invocation(
        original=lambda: None,
        target=lambda: None,
        environment=environment,
        call=call,
    )

    # Basic attribute passthrough
    assert inv.name == "cmd"
    assert inv.args == (1, 2)
    assert inv.kwargs["a"] == 3

    # Shared state is mutable and persists across reads/writes.
    inv.state["k"] = "v"
    assert inv.state == {"k": "v"}


def test_invocation_environment_with_context_returns_copy():
    env = InvocationEnvironment(app="app", name="n", context=None)
    env2 = env.with_context({"ctx": 1})
    assert env2 is not env
    assert env.context is None
    assert env2.context == {"ctx": 1}


def test_invocation_call_clone_overrides_and_copies():
    call = InvocationCall(args=(1, 2), kwargs={"x": 3})
    clone = call.clone(args=(9,), kwargs={"y": 7})
    assert clone.args == (9,)
    assert clone.kwargs == {"y": 7}
    # original unchanged
    assert call.args == (1, 2)
    assert call.kwargs == {"x": 3}


def test_resolve_call_arguments_various_kinds_and_virtuals():
    def target(ctx: InvocationContext, a, /, b, *args, kwonly, **kwargs):
        return (
            "ok",
            isinstance(ctx, InvocationContext),
            a,
            b,
            args,
            kwonly,
            kwargs,
        )

    # Publish metadata expected by Invocation.resolve_call_arguments
    target.__typerplus_original_signature__ = inspect.signature(target)
    target.__typerplus_context_param_names__ = ("ctx",)
    target.__typerplus_virtual_param_names__ = ("virt",)

    env = InvocationEnvironment(app=None, name="demo", context=None)
    call = InvocationCall(
        args=(10, 20, 30), kwargs={"kwonly": 40, "virt": True, "xtra": 50}
    )
    inv = Invocation(original=target, target=target, environment=env, call=call)

    result = inv.invoke_target()
    assert result[0] == "ok"
    assert result[1] is True
    # positional-only a, followed by b from args, and *args collects the rest
    assert result[2] == 10
    assert result[3] == 20
    assert result[4] == (30,)
    # kw-only collected from kwargs
    assert result[5] == 40
    # **kwargs must not include virtual param; only the extra remains
    assert result[6] == {"xtra": 50}


def test_invocation_context_helpers():
    env = InvocationEnvironment(app="app", name="cmd", context={"hello": True})
    call = InvocationCall(args=(), kwargs={})
    inv = Invocation(
        original=lambda: None, target=lambda: None, environment=env, call=call
    )

    ctx = inv.command_context
    # properties mirror invocation
    assert ctx.app == "app"
    assert ctx.name == "cmd"
    assert ctx.click_context == {"hello": True}
    # state passthrough and get convenience
    ctx.state["k"] = "v"
    assert ctx.get_state("k") == "v"
    assert ctx.get_state("missing", 3) == 3

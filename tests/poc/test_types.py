from testproj import Invocation


def test_invocation_dataclass_fields_and_state():
    """Validate Invocation fields pass through and its mutable state dict persists values."""
    # Invocation is the context object the pipeline passes through middlewares
    # and into the base handler. It carries metadata and a shared, mutable
    # state dict that middlewares can read/write.
    inv = Invocation(
        app=None,
        original=lambda: None,
        target=lambda: None,
        args=(1, 2),
        kwargs={"a": 3},
        name="cmd",
    )

    # Basic attribute passthrough
    assert inv.name == "cmd"
    assert inv.args == (1, 2)
    assert inv.kwargs["a"] == 3

    # Shared state is mutable and persists across reads/writes.
    inv.state["k"] = "v"
    assert inv.state == {"k": "v"}

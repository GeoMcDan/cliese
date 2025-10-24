import inspect

from typerplus.signature import (
    apply_runtime_view,
    default_or,
    exec_signature,
    is_empty,
    kw_only_param,
    runtime_signature,
    set_signature,
    signature_of,
)
from typerplus.types import InvocationContext


def test_signature_of_and_set_signature_roundtrip():
    def user(a: int) -> int:
        return a

    sig = signature_of(user)
    assert sig is not None
    assert str(sig) == str(inspect.signature(user))

    # Overwrite with an altered signature and verify `inspect.signature` sees it
    new = inspect.Signature(parameters=(), return_annotation=sig.return_annotation)
    set_signature(user, new)
    seen = signature_of(user)
    assert seen is not None
    assert str(seen) == str(new)


def test_apply_runtime_view_sets_metadata_and_visible_signature():
    def command(ctx: InvocationContext, x: int) -> str:  # pragma: no cover - shape only
        return "ok"

    original = inspect.signature(command)
    params = list(original.parameters.values())
    # drop the first parameter (ctx)
    runtime = original.replace(parameters=params[1:])

    apply_runtime_view(
        command,
        original=original,
        runtime=runtime,
        hidden_names=("ctx",),
    )

    # metadata attributes are present
    assert getattr(command, "__typerplus_original_signature__") is original
    assert getattr(command, "__typerplus_runtime_signature__") is runtime
    assert getattr(command, "__typerplus_context_param_names__") == ("ctx",)

    # visible signature reflects runtime
    assert str(inspect.signature(command)) == str(runtime)
    # helper accessors prefer the right view
    assert str(exec_signature(command)) == str(original)
    assert str(runtime_signature(command)) == str(runtime)


def test_kw_only_param_builder():
    p = kw_only_param("flag", bool, True)
    assert p.kind is inspect.Parameter.KEYWORD_ONLY
    assert p.name == "flag"
    assert p.annotation is bool
    assert p.default is True


def test_is_empty_and_default_or():
    assert is_empty(inspect.Signature.empty)
    assert default_or(inspect.Signature.empty, None) is None
    assert default_or(5, None) == 5


def test_signature_of_handles_typeerror_and_valueerror_cases():
    # TypeError: non-callable object
    assert signature_of(123) is None

    # ValueError: attribute-based failure when reading __signature__
    class _Raise:
        def __get__(self, obj, owner):  # pragma: no cover - indirect path
            raise ValueError("boom")

    class BadSig:
        def __call__(self):  # pragma: no cover - shape only
            return None

        __signature__ = _Raise()

    bad = BadSig()
    assert signature_of(bad) is None


def test_exec_signature_returns_empty_when_signature_unavailable():
    # Non-callable: signature_of returns None -> exec_signature falls back to empty signature
    sig = exec_signature(123)
    assert isinstance(sig, inspect.Signature)
    assert list(sig.parameters) == []


def test_runtime_signature_falls_back_when_runtime_missing():
    # Case 1: signature_of returns None -> empty signature
    sig1 = runtime_signature(123)
    assert isinstance(sig1, inspect.Signature)
    assert list(sig1.parameters) == []

    # Case 2: signature_of returns a real signature
    def user(a: int, b: int = 0):  # pragma: no cover - shape only
        return a + b

    sig2 = runtime_signature(user)
    assert str(sig2) == str(inspect.signature(user))


def test_apply_runtime_view_sets_virtual_names_tuple():
    def command(x: int):  # pragma: no cover - shape only
        return x

    original = inspect.signature(command)
    runtime = original
    apply_runtime_view(
        command,
        original=original,
        runtime=runtime,
        virtual_names=("what_if", "debug"),
    )
    assert getattr(command, "__typerplus_virtual_param_names__") == ("what_if", "debug")
    # sanity: visible signature remains set
    assert str(inspect.signature(command)) == str(runtime)

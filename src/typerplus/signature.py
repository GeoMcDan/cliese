from __future__ import annotations

import inspect
from typing import Any, Callable, Iterable


def signature_of(func: Callable[..., Any]) -> inspect.Signature | None:
    """Return the function's signature or None if it cannot be inspected.

    Uses `inspect.signature` which honors a callable's `__signature__` if set.
    Catches `TypeError`/`ValueError` that can occur for builtins or objects
    not providing a Python inspectable signature.
    """

    try:
        return inspect.signature(func)
    except (TypeError, ValueError):
        return None


def set_signature(func: Callable[..., Any], sig: inspect.Signature) -> None:
    """Assign a concrete signature to a callable via `__signature__`."""

    func.__signature__ = sig


def ensure_signature(func: Callable[..., Any]) -> inspect.Signature | None:
    """Ensure the callable exposes a concrete `inspect.Signature`.

    If `__signature__` is missing, derive one via `inspect.signature` and set it.
    Returns the resulting signature when available, else None.
    """

    current = getattr(func, "__signature__", None)
    if current is not None:
        return current
    sig = signature_of(func)
    if sig is not None:
        set_signature(func, sig)
    return sig


def exec_signature(func: Callable[..., Any]) -> inspect.Signature:
    """Return the signature to use when binding/forwarding call arguments.

    Prefers an `__typerplus_original_signature__` when present; otherwise falls
    back to the current visible signature (which may come from `__signature__`).
    """

    original = getattr(func, "__typerplus_original_signature__", None)
    if original is not None:
        return original
    sig = signature_of(func)
    if sig is None:
        # As a last resort, construct an empty signature to avoid crashes.
        return inspect.Signature()
    return sig


def runtime_signature(func: Callable[..., Any]) -> inspect.Signature:
    """Return the signature Typer should see during command registration.

    Prefers `__typerplus_runtime_signature__` when set, else the visible one.
    """

    runtime = getattr(func, "__typerplus_runtime_signature__", None)
    if runtime is not None:
        return runtime
    sig = signature_of(func)
    if sig is None:
        return inspect.Signature()
    return sig


def apply_runtime_view(
    func: Callable[..., Any],
    *,
    original: inspect.Signature,
    runtime: inspect.Signature,
    hidden_names: Iterable[str] = (),
    virtual_names: Iterable[str] = (),
) -> None:
    """Publish a runtime signature while tracking metadata TyperPlus relies on.

    - Writes `__typerplus_original_signature__` and `__typerplus_runtime_signature__`.
    - Stores the provided `hidden_names` under `__typerplus_context_param_names__`.
    - Stores the provided `virtual_names` under `__typerplus_virtual_param_names__`.
    - Sets `__signature__` to the runtime signature for Typer/inspect to see.
    """

    setattr(func, "__typerplus_original_signature__", original)
    setattr(func, "__typerplus_runtime_signature__", runtime)
    if hidden_names:
        setattr(func, "__typerplus_context_param_names__", tuple(hidden_names))
    if virtual_names:
        setattr(func, "__typerplus_virtual_param_names__", tuple(virtual_names))
    set_signature(func, runtime)


def kw_only_param(name: str, annotation: Any, default: Any) -> inspect.Parameter:
    """Create a KEYWORD_ONLY parameter with the provided annotation/default."""

    return inspect.Parameter(
        name,
        kind=inspect.Parameter.KEYWORD_ONLY,
        annotation=annotation,
        default=default,
    )


def pos_or_kw_param(name: str, annotation: Any, default: Any) -> inspect.Parameter:
    """Create a POSITIONAL_OR_KEYWORD parameter with the provided annotation/default."""

    return inspect.Parameter(
        name,
        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=annotation,
        default=default,
    )


def is_empty(value: Any) -> bool:
    """True when a value represents an 'empty' default from inspect APIs."""

    return value in (
        inspect.Signature.empty,
        inspect.Parameter.empty,
        getattr(inspect, "_empty", object()),
    )


def default_or(value: Any, fallback: Any) -> Any:
    """Return fallback when the given value is an 'empty' sentinel."""

    return fallback if is_empty(value) else value

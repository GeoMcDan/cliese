from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter, Signature, signature

from testproj.legacy.signature.nodes import ParameterKind


@dataclass(frozen=True)
class ParamNode:
    name: str
    kind: ParameterKind
    annotation: object = Signature.empty
    default: object = Signature.empty
    raw: Parameter | None = None


@dataclass(frozen=True)
class ReturnNode:
    annotation: object = Signature.empty


@dataclass(frozen=True)
class SigNode:
    func: object
    params: tuple[ParamNode, ...]
    returns: ReturnNode | None = None


def build_sig_node(func) -> SigNode:
    sig = signature(func)
    nodes = tuple(
        ParamNode(p.name, ParameterKind(p.Kind), p.annotation, p.default, p)
        for p in sig.parameters.values()
    )
    return SigNode(func, nodes, ReturnNode(sig.return_annotation))

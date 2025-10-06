import abc
import dataclasses
import inspect
import typing
from collections.abc import Iterable as ABCIterable
from dataclasses import dataclass
from enum import IntEnum
from typing import Mapping, override


class ParameterKind(IntEnum):
    POS_ONLY = inspect.Parameter.POSITIONAL_ONLY.value
    POS_OR_KW = inspect.Parameter.POSITIONAL_OR_KEYWORD.value
    VAR_POS = inspect.Parameter.VAR_POSITIONAL.value
    VAR_KW = inspect.Parameter.VAR_KEYWORD.value
    KW_ONLY = inspect.Parameter.KEYWORD_ONLY.value


class SigElementBase:
    def accept(self, visitor: "SigVisitorBase"):
        visitor.visit(self)


class SigVisitorBase(abc.ABC):
    @abc.abstractmethod
    def visit(self, sig_elem: SigElementBase):
        pass


@dataclass(frozen=True)
class SigNameElement(SigElementBase):
    name: str


@dataclass(frozen=True)
class SigParamElement(SigElementBase):
    param: object = dataclasses.field(repr=False, kw_only=True)
    param_name: str = dataclasses.field(kw_only=True)
    param_default: object = dataclasses.field(kw_only=True)
    param_annotation: type = dataclasses.field(kw_only=True)
    param_kind: ParameterKind = dataclasses.field(kw_only=True)

    @classmethod
    def from_param(cls, name, param: inspect.Parameter):
        assert name == param.name
        return cls(
            param=param,
            param_name=name,
            param_default=param.default,
            param_annotation=param.annotation,
            param_kind=ParameterKind(param.kind),
        )

    def __repr__(self):
        annotation = self.param_annotation

        if annotation is None:
            annotation = ": None"
        if annotation is inspect.Parameter.empty:
            annotation = ""
        elif hasattr(annotation, "__qualname__"):
            annotation = ": " + annotation.__qualname__
        elif hasattr(annotation, "__name__"):
            annotation = ": " + annotation.__name__
        else:
            annotation = ": " + repr(annotation)

        default = ""
        if self.param_default is not inspect.Parameter.empty:
            default = f" = {self.param_default}"
        return f"{self.param_name}{annotation}{default}"


@dataclass(frozen=True)
class SigReturnElement(SigElementBase):
    annotation: type

    def __repr__(self):
        if hasattr(self.annotation, "__qualname__"):
            return f"-> {self.annotation.__qualname__}"
        elif hasattr(self.annotation, "__name__"):
            return f"-> {self.annotation.__name__}"
        elif self.annotation is None:
            return "-> None"
        else:
            return f"-> {repr(self.annotation)}"


@dataclass(frozen=True, init=False)
class SigParamGroupElement(SigElementBase, ABCIterable):
    parameters: typing.Iterable[SigParamElement]

    def __init__(self, params: typing.Iterable):
        if isinstance(params, Mapping):
            params = params.values()
        elif not isinstance(params, ABCIterable):
            raise TypeError("params must be an iterable")

        parameters = (
            (
                param
                if isinstance(param, SigParamElement)
                else SigParamElement.from_param(param.name, param)
            )
            for param in params
        )
        object.__setattr__(self, "parameters", list(parameters))

    def __iter__(self):
        yield from self.parameters

    @override
    def accept(self, visitor):
        visitor.visit(self)
        for param in self:
            param.accept(visitor)

    def __repr__(self):
        return (
            f'SigParamGroupElement("({", ".join(repr(p) for p in self.parameters)})")'
        )


@dataclass(init=False)
class SigElement(SigElementBase, ABCIterable):
    name: SigNameElement
    parameters: SigParamGroupElement
    return_: SigReturnElement

    def __init__(self, func):
        sig = inspect.signature(func)
        self.name = SigNameElement(func.__name__)
        self.parameters = SigParamGroupElement(sig.parameters)
        self.return_ = SigReturnElement(sig.return_annotation)

    def __iter__(self):
        yield self.name
        yield self.parameters
        yield self.return_

    @override
    def accept(self, visitor):
        visitor.visit(self)
        for elem in self:
            elem.accept(visitor)

    def __repr__(self):
        return f'SigElement("{self.name}", "{self.parameters}", "{self.return_}")'

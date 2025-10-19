import inspect
from typing import Any

from .nodes import ParameterKind


class SigBuilder:
    """
    Build a inspect.signature
    """

    def __init__(self):
        self.signature = inspect.Signature()
        self.params = []

    def add_parameter(
        self,
        name: str,
        /,
        kind: ParameterKind = inspect.Parameter.POSITIONAL_OR_KEYWORD,
        *,
        default: Any = inspect.Parameter.empty,
        annotation: Any = inspect.Parameter.empty,
    ):
        param = inspect.Parameter(
            name=name, kind=kind, default=default, annotation=annotation
        )
        self.params.append(param)
        self.signature = self.signature.replace(parameters=self.params)
        return self

    def add_return_annotation(self, annotation: Any = inspect.Signature.empty):
        self.signature = self.signature.replace(return_annotation=annotation)
        return self

    def build(self):
        return self.signature

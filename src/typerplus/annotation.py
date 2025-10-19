from __future__ import annotations

import types
import typing
from dataclasses import dataclass
from functools import reduce
from operator import or_
from typing import Any, Iterable, Tuple, Type

from typer.models import ParameterInfo


def _strip_optional(annotation: Any) -> tuple[Any, bool]:
    """Return (inner_type, was_optional) for Optional/Union[None] annotations."""

    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if origin is typing.Optional:
        return args[0], True

    if origin in (typing.Union, types.UnionType):
        non_none = tuple(arg for arg in args if arg is not type(None))  # noqa: E721
        optional = len(non_none) < len(args)
        if not non_none:
            return annotation, optional
        if len(non_none) == 1:
            return non_none[0], optional
        return reduce(or_, non_none), optional

    return annotation, False


@dataclass(init=False)
class TyperAnnotation:
    """Introspect and rebuild typing.Annotated/Optional combinations."""

    annotated: bool
    type: Type[Any] | Any
    annotations: Tuple[Any, ...]
    optional: bool

    def __init__(self, annotation: Any):
        self.original_annotation = annotation
        self.annotated = False
        self.annotations = ()

        base_annotation = annotation
        if typing.get_origin(annotation) is typing.Annotated:
            base_annotation, *metadata = typing.get_args(annotation)
            self.annotated = True
            self.annotations = tuple(metadata)

        unwrapped, optional = _strip_optional(base_annotation)
        self.type = unwrapped
        self.optional = optional

    # Metadata helpers -------------------------------------------------
    def find_parameter_info_arg(self):
        for param in self.annotations:
            if isinstance(param, ParameterInfo):
                yield param

    def metadata_without_parameter_info(self) -> tuple[Any, ...]:
        return tuple(
            meta for meta in self.annotations if not isinstance(meta, ParameterInfo)
        )

    # Reconstruction helpers -------------------------------------------
    def rebuild(
        self,
        *,
        annotation_type: Any | None = None,
        annotations: Iterable[Any] | None = None,
        optional: bool | None = None,
    ) -> Any:
        """Return a rebuilt annotation, preserving optional/metadata semantics."""

        typ = annotation_type if annotation_type is not None else self.type
        use_optional = self.optional if optional is None else optional

        if use_optional:
            typ = typing.Optional[typ]

        metadata = tuple(annotations) if annotations is not None else self.annotations
        if metadata:
            return typing.Annotated[typ, *metadata]
        return typ

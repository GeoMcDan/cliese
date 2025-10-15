import types
import typing
from functools import reduce
from operator import or_

from typer.models import ParameterInfo


class TyperAnnotation:
    def find_parameter_info_arg(self):
        if not self.annotations:
            return

        for param in self.annotations:
            if isinstance(param, ParameterInfo):
                yield param

    def __init__(self, annotation):
        # TODO: type normalization for typer compatibility? that a necessary thing?
        self.original_annotation = annotation

        # unpack Annotated arguments
        match (typing.get_origin(annotation), typing.get_args(annotation)):
            case (typing.Annotated, (inner_type, *parameter)):
                self.annotated = True
                self.type = inner_type
                self.annotations = parameter

            case _:
                self.type = annotation
                self.annotated = False
                self.annotations = ()

        # unpack optional parameters
        self.optional = False
        types_ = None
        match (typing.get_origin(self.type), typing.get_args(self.type)):
            case (typing.Optional, inner_type):
                self.type = inner_type
                self.optional = True

            case (typing.Union | types.UnionType, (*inner_types, types.NoneType)):
                self.optional = True
                types_ = inner_types

            case (typing.Union | types.UnionType, inner_types):
                pass

            case (None, ()):
                pass
            case (a, b):
                print("a:", a)
                print("b:", b)
            case _:
                raise TypeError("Unsupported inner type", inner_type)

        print("types: %s" % types_)
        match types_:
            case () | None:  # no inner types
                pass
            case (only,):  # single element tuple
                self.type = only
            case a:
                # fold with `|` → t1 | t2 | t3 ...
                self.type = reduce(or_, types_)

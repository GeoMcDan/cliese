import logging
from typing import Annotated, Optional

import typer

from typerplus.annotation import TyperAnnotation


def test_typer_annotation_parses_optional_and_metadata():
    option = typer.Option("--verbose", "-v")
    sentinel = object()

    annotated = Annotated[Optional[logging.Logger], option, sentinel]
    view = TyperAnnotation(annotated)

    assert view.optional is True
    assert view.type is logging.Logger
    assert tuple(view.find_parameter_info_arg()) == (option,)
    assert view.metadata_without_parameter_info() == (sentinel,)

    rebuilt = view.rebuild(annotations=(sentinel,))
    assert rebuilt == Annotated[Optional[logging.Logger], sentinel]


def test_typer_annotation_rebuild_updates_type_and_optional():
    annotated = Annotated[int, "meta"]
    view = TyperAnnotation(annotated)

    new_annotation = view.rebuild(
        annotation_type=str,
        annotations=("meta",),
        optional=True,
    )

    assert new_annotation == Annotated[Optional[str], "meta"]

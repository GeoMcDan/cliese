import inspect
from inspect import Signature

from testproj.legacy.signature.builder import SigBuilder
from testproj.legacy.signature.nodes import ParameterKind


def test_placeholder():
    builder = SigBuilder()
    assert builder is not None

    builder.add_parameter("x", ParameterKind.POS_ONLY, annotation=int, default=0)
    print("One parameter added (kw_or_pos):", builder.signature)
    assert str(builder.signature) == "(x: int = 0, /)"

    builder.add_parameter("y", ParameterKind.POS_OR_KW, annotation=str, default="")
    print("Second param:", builder.signature)
    assert str(builder.signature) == "(x: int = 0, /, y: str = '')"

    builder.add_parameter("z", ParameterKind.VAR_POS)
    print("Third param:", builder.signature)
    assert str(builder.signature) == "(x: int = 0, /, y: str = '', *z)"

    builder.add_parameter("a", ParameterKind.KW_ONLY, annotation=float, default=0.0)
    print("Fourth param:", builder.signature)
    assert str(builder.signature) == "(x: int = 0, /, y: str = '', *z, a: float = 0.0)"

    builder.add_parameter("b", ParameterKind.VAR_KW)
    print("Fifth param:", builder.signature)
    assert (
        str(builder.signature)
        == "(x: int = 0, /, y: str = '', *z, a: float = 0.0, **b)"
    )

    builder.add_return_annotation(annotation=bool)
    print("With return annotation:", builder.signature)

    assert (
        str(builder.signature)
        == "(x: int = 0, /, y: str = '', *z, a: float = 0.0, **b) -> bool"
    )
    assert builder.signature is builder.build()
    assert isinstance(builder.signature, Signature)


def test_chain_builder():
    sig = (
        SigBuilder()
        .add_parameter(
            "x", inspect.Parameter.POSITIONAL_ONLY, annotation=int, default=0
        )
        .add_parameter(
            "y", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str, default=""
        )
        .add_parameter("z", inspect.Parameter.VAR_POSITIONAL)
        .add_parameter(
            "a", inspect.Parameter.KEYWORD_ONLY, annotation=float, default=0.0
        )
        .add_parameter("b", inspect.Parameter.VAR_KEYWORD)
        .add_return_annotation(annotation=bool)
        .build()
    )

    print("Chained builder:", sig)
    assert str(sig) == "(x: int = 0, /, y: str = '', *z, a: float = 0.0, **b) -> bool"


def test_wrapper():
    sig = (
        SigBuilder()
        .add_parameter("args", inspect.Parameter.VAR_POSITIONAL)
        .add_parameter("kwargs", inspect.Parameter.VAR_KEYWORD)
    ).build()
    print("wrapper:", sig)
    assert str(sig) == "(*args, **kwargs)"


def test_wrapper2():
    sig = (
        SigBuilder()
        .add_parameter("args", inspect.Parameter.VAR_POSITIONAL)
        .add_parameter("kwargs", inspect.Parameter.VAR_KEYWORD)
    ).signature
    print("wrapper:", sig)
    assert str(sig) == "(*args, **kwargs)"


def test_build_with_param_pos_only():
    sig1 = (
        SigBuilder()
        .add_parameter("n", ParameterKind.POS_ONLY, annotation=int)
        .signature
    )
    sig2 = (
        SigBuilder()
        .add_parameter("n", inspect.Parameter.POSITIONAL_ONLY, annotation=int)
        .signature
    )

    assert str(sig1) == str(sig2) == "(n: int, /)"
    assert sig1 == sig2


def test_build_with_param_pos_or_kw():
    sig1 = (
        SigBuilder()
        .add_parameter("n", ParameterKind.POS_OR_KW, annotation=int)
        .signature
    )
    sig2 = (
        SigBuilder()
        .add_parameter("n", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int)
        .signature
    )

    assert str(sig1) == str(sig2) == "(n: int)"
    assert sig1 == sig2


def test_build_with_param_kw_only():
    sig1 = SigBuilder().add_parameter("n", ParameterKind.KW_ONLY).signature
    sig2 = SigBuilder().add_parameter("n", inspect.Parameter.KEYWORD_ONLY).signature

    assert str(sig1) == str(sig2) == "(*, n)"
    print(str(sig1))
    assert sig1 == sig2


def test_build_with_no_param_kind():
    sig1 = SigBuilder().add_parameter("n", annotation=int).signature
    assert str(sig1) == "(n: int)"


def test_build_with_return_annotation_none():
    sig2 = SigBuilder().add_return_annotation(None).signature
    assert str(sig2) == "() -> None"


def test_build_empty_signature():
    sig1 = SigBuilder().signature
    assert str(sig1) == "()"

    sig2 = SigBuilder().add_return_annotation(Signature.empty).signature
    assert str(sig2) == "()"


def test_build_with_empty_param_annotation():
    sig1 = SigBuilder().add_parameter("n", annotation=inspect.Parameter.empty).signature
    assert str(sig1) == "(n)"

import inspect
import logging

import pytest

from testproj.signature.nodes import (
    SigElement,
    SigNameElement,
    SigParamGroupElement,
    SigReturnElement,
)
from testproj.signature.visitor import SigVisitor, SigVisitorPrint

logger = logging.getLogger(__name__)


def _test1(
    j: int, k: str, /, m: str = None, *, u: int = 0, v: str = None, **kwargs
) -> None: ...


def _test2(j: int, *args, abc=2, **kwargs) -> int: ...


def _test3(): ...


def signature_generator(func):
    sig = inspect.signature(func)

    yield SigNameElement(func.__name__)
    yield SigParamGroupElement(sig.parameters)
    yield SigReturnElement(sig.return_annotation)


@pytest.mark.quick
def test_iterator():
    gen = signature_generator(_test1)
    visitor = SigVisitor()
    for item in gen:
        item.accept(visitor)
        # logger.debug("Item: %s", item)

    assert (
        visitor.signature
        == "_test1(j: int, k: str, /, m: str = None, *, u: int = 0, v: str = None, **kwargs) -> None"
    )


def test_sigelement_test2_with_sig_builder():
    gen = SigElement(_test2)  # signature_generator(_test2)
    visitor = SigVisitor()
    gen.accept(visitor)
    print(visitor.signature)
    assert visitor.signature == "_test2(j: int, *args, *, abc = 2, **kwargs) -> int"


def test_sigelement_test3_with_sig_print():
    gen = SigElement(_test2)  # signature_generator(_test3)
    visitor = SigVisitorPrint()
    gen.accept(visitor)


def test_sigelement_test3_with_sig_builder():
    gen = SigElement(_test3)  # signature_generator(_test3)
    visitor = SigVisitor()
    gen.accept(visitor)
    print(visitor.signature)
    assert visitor.signature == "_test3()"


def test_sigelement_test1_with_sig_builder():
    gen = SigElement(_test1)  # signature_generator(_test2)
    # for item in gen:
    #    logger.debug("Item: %s", item)

    visitor = SigVisitor()
    gen.accept(visitor)

    print(visitor.signature)
    assert (
        visitor.signature
        == "_test1(j: int, k: str, /, m: str = None, *, u: int = 0, v: str = None, **kwargs) -> None"
    )

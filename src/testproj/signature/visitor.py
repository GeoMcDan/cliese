import inspect
from functools import singledispatchmethod

from testproj.signature.nodes import (
    ParameterKind,
    SigElement,
    SigElementBase,
    SigNameElement,
    SigParamElement,
    SigParamGroupElement,
    SigReturnElement,
    SigVisitorBase,
)


class SigVisitor(SigVisitorBase):
    def __init__(self):
        self.params = []
        self.kinds = []
        self.signature = ""

    @singledispatchmethod
    def visit(self, sig_elem: SigElementBase):
        pass

    @visit.register
    def _(self, sig_elem: SigElement):
        pass

    @visit.register
    def _(self, sig_elem: SigParamElement):
        txt = sig_elem.param_name

        if sig_elem.param_kind == ParameterKind.VAR_POS:
            txt = "*" + txt
        elif sig_elem.param_kind == ParameterKind.VAR_KW:
            txt = "**" + txt

        if sig_elem.param_annotation is not inspect.Parameter.empty:
            if hasattr(sig_elem.param_annotation, "__qualname__"):
                txt += ": " + sig_elem.param_annotation.__qualname__
            else:
                txt += ": " + str(sig_elem.param_annotation)

        if sig_elem.param_default is not inspect.Parameter.empty:
            txt += " = " + str(sig_elem.param_default)

        if len(self.kinds) > 0:
            prev = self.kinds[-1]
            if sig_elem.param_kind != prev:
                match sig_elem.param_kind:
                    case ParameterKind.POS_OR_KW:
                        self.params.append("/")
                    case ParameterKind.KW_ONLY:
                        self.params.append("*")

        self.params.append(txt)
        self.kinds.append(sig_elem.param_kind)

    @visit.register
    def _(self, sig_elem: SigParamGroupElement):
        peek_visit = SigVisitor()

        self.params.clear()
        for param in sig_elem:
            param.accept(peek_visit)

        txt = ", ".join(p for p in peek_visit.params)
        self.params.clear()

        self.signature += f"({txt})"

    @visit.register
    def _(self, sig_elem: SigNameElement):
        self.signature += sig_elem.name

    @visit.register
    def _(self, sig_elem: SigReturnElement):
        if sig_elem.annotation is None:
            self.signature += " -> None"
        elif sig_elem.annotation is inspect.Signature.empty:
            pass
        elif sig_elem.annotation:
            if hasattr(sig_elem.annotation, "__qualname__"):
                self.signature += " -> " + sig_elem.annotation.__qualname__
            elif hasattr(sig_elem.annotation, "__name__"):
                self.signature += " -> " + sig_elem.annotation.__name__
            else:
                self.signature += " -> " + repr(sig_elem.annotation)
        elif sig_elem.annotation:
            self.signature += " -> " + sig_elem.annotation.__qualname__


class SigVisitorPrint(SigVisitorBase):
    def __init__(self):
        self.params = []
        self.kinds = []

    @singledispatchmethod
    def visit(self, sig_elem: SigElementBase):
        print("SigElementBase:", sig_elem)

    @visit.register
    def _(self, sig_elem: SigElement):
        print("SigElement:", sig_elem)

    @visit.register
    def _(self, sig_elem: SigParamElement):
        txt = sig_elem.param_name

        if sig_elem.param_kind == ParameterKind.VAR_POS:
            txt = "*" + txt
        elif sig_elem.param_kind == ParameterKind.VAR_KW:
            txt = "**" + txt

        if sig_elem.param_annotation is not inspect.Parameter.empty:
            if hasattr(sig_elem.param_annotation, "__qualname__"):
                txt += ": " + sig_elem.param_annotation.__qualname__
            else:
                txt += ": " + str(sig_elem.param_annotation)

        if sig_elem.param_default is not inspect.Parameter.empty:
            txt += " = " + str(sig_elem.param_default)

        if len(self.kinds) > 0:
            prev = self.kinds[-1]
            if sig_elem.param_kind != prev:
                match sig_elem.param_kind:
                    case ParameterKind.POS_OR_KW:
                        self.params.append("/")
                    case ParameterKind.KW_ONLY:
                        self.params.append("*")

        self.params.append(txt)
        self.kinds.append(sig_elem.param_kind)

        print("SigParamElement:", txt)

    @visit.register
    def _(self, sig_elem: SigParamGroupElement):
        # for param in sig_elem:
        #    param.accept(self)

        print("SigParamGroupElement:", sig_elem)

    @visit.register
    def _(self, sig_elem: SigNameElement):
        print("SigNameElement:", sig_elem)

    @visit.register
    def _(self, sig_elem: SigReturnElement):
        print("SigReturnElement:", sig_elem)

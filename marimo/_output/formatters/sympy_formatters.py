# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory


def patch_sympy(*objs: Any) -> None:
    """Adds the _mime_() method to sympy objects
    e.g.
    Symbol._mime_ = sympy_html
    example:
    patch_sympy(Symbol, Integral)
    """
    from sympy import latex  # type: ignore

    from marimo._output.md import md

    for obj in objs:
        # the lambda below is our sympy_html
        obj._mime_ = lambda obj: (
            "text/html",
            md(f"""\\[{latex(obj)}\\]""").text,
        )


def sympy_as_html(obj: Any) -> tuple[KnownMimeType, str]:
    """Creates HTML output from a Printable Sympy object
    e.g.

    Example:
    integral = Integral(x**2, x)
    sympy_as_html(integral)
    """
    from sympy import latex

    from marimo._output.md import md

    return ("text/html", md(f"""\\[{latex(obj)}\\]""").text)


class SympyFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "sympy"

    def register(self) -> None:
        from sympy.core.basic import Printable  # type: ignore

        # We will monkey-patch the Printable class so most Sympy constructs
        # that can be "pretty-printed" with sympy.latex
        # can also be rendered in marimo.
        # One way to test if an expression is supported is
        # with latex(expr)
        # e.g. latex(x**2) --> x^{2}
        patch_sympy(Printable)

        # from marimo._output import formatting
        # @formatting.formatter(Integral)
        # def _show_integral(integral: Integral) -> tuple[KnownMimeType, str]:
        #    return sympy_as_html(integral)

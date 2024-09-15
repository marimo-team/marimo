from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.formatters import register_formatters
from marimo._output.formatting import (
    get_formatter,
)

HAS_DEPS = DependencyManager.sympy.has()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_sympy_formatters_basic_symbols() -> None:
    register_formatters()

    from sympy import symbols

    x, y = symbols("x y")

    # x Symbol
    formatter = get_formatter(x, include_opinionated=False)
    assert formatter
    mime, content = formatter(x)
    assert mime == "text/html"
    assert content.find(r"||[x||]") > 0

    # y Symbol
    formatter = get_formatter(y, include_opinionated=False)
    assert formatter
    mime, content = formatter(y)
    assert mime == "text/html"
    assert content.find(r"||[y||]") > 0


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_sympy_formatters_addition() -> None:
    register_formatters()

    from sympy import symbols

    x, y, z = symbols("x y z")
    out_exp = x + y + z
    # x + y + z
    formatter = get_formatter(out_exp, include_opinionated=False)
    assert formatter
    mime, content = formatter(out_exp)
    assert mime == "text/html"
    assert content.find("||[x + y + z||]") > 0


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_sympy_formatters_power() -> None:
    register_formatters()

    from sympy import symbols

    x, y, z = symbols("x y z")
    x_squared = x**2

    # x^2
    formatter = get_formatter(x_squared, include_opinionated=False)
    assert formatter
    mime, content = formatter(x_squared)
    assert mime == "text/html"
    assert content.find("||[x^{2}||]") > 0


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_sympy_formatters_matrix() -> None:
    register_formatters()

    from sympy import Matrix, symbols

    x, y, z = symbols("x y z")

    # numeric matrix
    M = Matrix([[1, 2], [3, 4]])
    B = Matrix([[1 * x, 2 * y], [z, 4]])

    # numeric matrix
    formatter = get_formatter(M, include_opinionated=False)
    assert formatter
    mime, content = formatter(M)
    assert mime == "text/html"
    assert (
        content.find(
            r"||[\left[\begin{matrix}1 &amp; 2\\3 &amp; 4\end{matrix}\right]||]"  # noqa: E501
        )
        > 0
    )
    # symbolic matrix
    formatter = get_formatter(B, include_opinionated=False)
    assert formatter
    mime, content = formatter(B)
    assert mime == "text/html"
    assert (
        content.find(
            r"||[\left[\begin{matrix}x &amp; 2 y\\z &amp; 4\end{matrix}\right]||]"  # noqa: E501
        )
        > 0
    )


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_sympy_formatters_Integral() -> None:
    register_formatters()

    from sympy import Integral, sqrt, symbols

    x, y, z = symbols("x y z")
    out_exp = Integral(sqrt(1 / x), x)

    # symbolic integral
    formatter = get_formatter(out_exp, include_opinionated=False)
    assert formatter
    mime, content = formatter(out_exp)
    assert mime == "text/html"
    assert content.find(r"||[\int \sqrt{\frac{1}{x}}\, dx||]") > 0

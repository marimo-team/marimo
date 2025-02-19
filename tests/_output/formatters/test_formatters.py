from __future__ import annotations

import importlib
import os.path
import sys
from typing import Any
from unittest.mock import Mock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatters import register_formatters
from marimo._output.formatting import (
    Plain,
    as_dom_node,
    as_html,
    formatter,
    get_formatter,
    try_format,
)


def test_path_finder_find_spec() -> None:
    # exercises a bug surfaced in
    # https://github.com/marimo-team/marimo/issues/763, in which find_spec
    # would fail because it was incorrectly patched
    register_formatters()

    spec = importlib.machinery.PathFinder.find_spec(
        "test_formatters", [os.path.dirname(__file__)]
    )
    assert spec is not None


HAS_DEPS = DependencyManager.pandas.has() and DependencyManager.polars.has()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_formatters_with_opinionated_formatter() -> None:
    register_formatters()

    import pandas as pd
    import polars as pl

    pd_df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})
    pl_df = pl.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})

    # Happy path
    obj = ["test"]
    formatter = get_formatter(obj)
    assert formatter is not None
    assert formatter(obj) == ("application/json", '["test"]')

    # With Plain
    obj = Plain(["test"])
    formatter = get_formatter(obj)
    assert formatter is not None
    assert formatter(obj) == ("application/json", '["test"]')

    # With pandas DataFrame
    formatter = get_formatter(pd_df)
    assert formatter is not None
    mime, content = formatter(pd_df)
    assert mime == "text/html"
    assert "<marimo-table" in content

    # With plain DataFrame + Plain
    obj = Plain(pd_df)
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "text/html"
    assert "<marimo-table" not in content

    # With polars DataFrame
    formatter = get_formatter(pl_df)
    assert formatter is not None
    mime, content = formatter(pl_df)
    assert mime == "text/html"
    assert "<marimo-table" in content

    # With plain DataFrame + Plain
    obj = Plain(pl_df)
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "text/html"
    assert "<marimo-table" not in content


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_as_html_opinionated_formatter():
    register_formatters()

    import pandas as pd
    import polars as pl

    pd_df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})
    pl_df = pl.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})

    # With pandas DataFrame
    html = as_html(pd_df)
    assert "<marimo-table" in html.text

    # With polars DataFrame
    html = as_html(pl_df)
    assert "<marimo-table" in html.text

    # With pandas DataFrame + Plain
    html = as_html(Plain(pd_df))
    assert "<marimo-table" not in html.text

    # With polars DataFrame + Plain
    html = as_html(Plain(pl_df))
    assert "<marimo-table" not in html.text


def test_broken_formatter():
    class _ClsForBrokenFormatter: ...

    def _format(cls: _ClsForBrokenFormatter) -> tuple[KnownMimeType, str]:
        del cls
        raise BaseException("Broken Formatter")  # noqa: TRY002

    formatter(_ClsForBrokenFormatter)(_format)

    obj = _ClsForBrokenFormatter()
    formatted = try_format(obj)
    assert formatted.traceback is not None
    assert "Broken Formatter" in formatted.traceback


@patch(
    "marimo._output.formatters.formatters.THIRD_PARTY_FACTORIES",
    new_callable=dict,
)
@patch.dict(sys.modules, {"fake_module": Mock()})
def test_pre_imported_formatter(mock_third_party_factories):
    mock_factory = Mock()
    mock_third_party_factories["fake_module"] = mock_factory

    register_formatters()
    assert mock_factory.register.call_count == 1


def test_repr_markdown():
    class ReprMarkdown:
        def _repr_markdown_(self):
            return "# Hello, World!"

    obj = ReprMarkdown()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "text/html"
    assert (
        content
        == '<span class="markdown prose dark:prose-invert"><h1 id="hello-world">Hello, World!</h1></span>'  # noqa: E501
    )


def test_repr_latex():
    class ReprLatex:
        def _repr_latex_(self):
            return r"$f(x) = e^x$"

    obj = ReprLatex()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "text/html"
    assert (
        content
        == '<span class="markdown prose dark:prose-invert"><span class="paragraph"><marimo-tex class="arithmatex">||(f(x) = e^x||)</marimo-tex></span></span>'  # noqa: E501
    )


def test_repr_html():
    class ReprHTML:
        def _repr_html_(self):
            return "<h1>Hello, World!</h1>"

    obj = ReprHTML()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "text/html"
    assert content == "<h1>Hello, World!</h1>"


def test_repr_html_with_script_tag_without_src():
    class ReprHTMLWithScriptTagWithoutSrc:
        def _repr_html_(self):
            return "<script>alert('Hello, World!')</script>"

    obj = ReprHTMLWithScriptTagWithoutSrc()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "text/html"
    assert (
        content
        == "<iframe srcdoc='&lt;script&gt;alert(&#x27;Hello, World!&#x27;)&lt;/script&gt;' width='100%' height='400px' onload='__resizeIframe(this)' frameborder='0'></iframe>"
    )


def test_repr_png():
    png = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABaElEQVR42mNk"

    class ReprPNG:
        def _repr_png_(self):
            return png

    obj = ReprPNG()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "image/png"
    assert content == png


def test_repr_jpeg():
    jpeg = "/9j/4AAQSkZJRgABAQEAYABgAAD/4QBoRXhpZgAATU0AKgAAAAgAA1IBAAAB"

    class ReprJPEG:
        def _repr_jpeg_(self):
            return jpeg

    obj = ReprJPEG()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "image/jpeg"
    assert content == jpeg


def test_repr_svg():
    svg = "<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100'></svg>"  # noqa: E501

    class ReprSVG:
        def _repr_svg_(self):
            return svg

    obj = ReprSVG()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "image/svg+xml"
    assert content == svg


def test_repr_json():
    class ReprJSON:
        def _repr_json_(self):
            return {"message": "Hello, World!"}

    obj = ReprJSON()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "application/json"
    assert content == {"message": "Hello, World!"}


def test_prefer_repr_html_over_repr_markdown():
    class ReprBoth:
        def _repr_html_(self):
            return "<h6>Hello, World!</h6>"

        def _repr_markdown_(self):
            return "# Hello, World!"

    obj = ReprBoth()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "text/html"
    assert content == "<h6>Hello, World!</h6>"


def test_repr_mimebundle():
    class ReprMimeBundle:
        def _repr_mimebundle_(self):
            return {
                "application/json": {"message": "Hello, World!"},
                "text/plain": "Hello, World!",
            }

    obj = ReprMimeBundle()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "application/vnd.marimo+mimebundle"
    assert content == {"application/json": {"message": "Hello, World!"}}


def test_repr_mimebundle_with_exclude():
    class ReprMimeBundle:
        def _repr_mimebundle_(self, include: Any = None, exclude: Any = None):
            del include, exclude
            return {
                "application/json": {"message": "Hello, World!"},
                "text/plain": "Hello, World!",
            }

    obj = ReprMimeBundle()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "application/vnd.marimo+mimebundle"
    assert content == {"application/json": {"message": "Hello, World!"}}


def test_repr_returns_none():
    class ReprNone:
        def _repr_html_(self):
            return None

        def _repr_json_(self):
            return "{}"

        def _repr_plain_(self):
            return "plain"

    obj = ReprNone()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "application/json"
    assert content == "{}"


def test_repr_empty_string():
    class ReprNone:
        def _repr_json_(self):
            return ""

        def _repr_plain_(self):
            return "plain"

    obj = ReprNone()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "application/json"
    assert content == ""


def test_as_dom_node():
    assert as_dom_node("test").text == "test"
    assert as_dom_node(123).text == "123"
    assert as_dom_node(123.456).text == "123.456"
    assert as_dom_node(None).text == "<span>None</span>"
    assert as_dom_node(True).text == "True"
    assert as_dom_node(False).text == "False"
    assert as_dom_node({"key": "value"}).text.startswith("<marimo-json")


class CustomList(list[int]):
    def _repr_html_(self):
        return f"<h1>{', '.join(map(str, self))}</h1>"


def test_format_extend_list():
    my_list = CustomList([1, 2, 3])
    assert as_dom_node(my_list).text == "<h1>1, 2, 3</h1>"


class CustomDict(dict[str, int]):
    def _repr_html_(self):
        return f"<h1>{', '.join(map(str, self.items()))}</h1>"


def test_format_extend_dict():
    my_dict = CustomDict({"a": 1, "b": 2, "c": 3})
    assert as_dom_node(my_dict).text == "<h1>('a', 1), ('b', 2), ('c', 3)</h1>"


class CustomTuple(tuple[int, int]):
    def _repr_html_(self):
        return f"<h1>{', '.join(map(str, self))}</h1>"


def test_format_extend_tuple():
    my_tuple = CustomTuple((1, 2, 3))
    assert as_dom_node(my_tuple).text == "<h1>1, 2, 3</h1>"


def test_repr_mimebundle_with_markdown():
    class ReprMimeBundleWithMarkdown:
        def _repr_mimebundle_(self):
            return {
                "text/markdown": "# Hello, World!",
            }

    obj = ReprMimeBundleWithMarkdown()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "application/vnd.marimo+mimebundle"
    assert content == {
        "text/html": '<span class="markdown prose dark:prose-invert"><h1 id="hello-world">Hello, World!</h1></span>',
        "text/markdown": "# Hello, World!",
    }

    # Does not convert markdown to html if html is already present
    class ReprMimeBundleWithMarkdownAndHtml:
        def _repr_mimebundle_(self):
            return {
                "text/html": "<h1>Hello, World!</h1>",
                "text/markdown": "# Hello, World!",
            }

    obj = ReprMimeBundleWithMarkdownAndHtml()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "application/vnd.marimo+mimebundle"
    assert content == {
        "text/html": "<h1>Hello, World!</h1>",
        "text/markdown": "# Hello, World!",
    }


def test_repr_mimebundle_with_latex():
    class ReprMimeBundleWithLatex:
        def _repr_mimebundle_(self):
            return {
                "text/latex": r"$e^x$",
            }

    obj = ReprMimeBundleWithLatex()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "application/vnd.marimo+mimebundle"
    assert content == {
        "text/html": '<span class="markdown prose dark:prose-invert"><span class="paragraph"><marimo-tex class="arithmatex">||(e^x||)</marimo-tex></span></span>',
        "text/latex": r"$e^x$",
    }


def test_display_protocol_takes_precedence() -> None:
    register_formatters()

    class Foo(list):
        def _display_(self):
            return "foo"

        def _repr_html_(self):
            return "<h1>Hello, World!</h1>"

    obj = Foo()
    formatter = get_formatter(obj)
    assert formatter is not None
    mime, content = formatter(obj)
    assert mime == "text/html"
    assert content == "<span>foo</span>"

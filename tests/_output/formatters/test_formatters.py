from __future__ import annotations

import importlib
import os.path
import sys
from typing import Any
from unittest.mock import Mock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.df_formatters import polars_dot_to_mermaid
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


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_lazyframe_renders_mermaid_html() -> None:
    register_formatters()

    import polars as pl

    ldf = pl.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]}).lazy()

    formatter = get_formatter(ldf)
    assert formatter is not None
    mimetype, contents = formatter(ldf)
    assert mimetype == "text/html"
    assert "<marimo-mermaid" in contents


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_polars_dot_to_mermaid() -> None:
    import polars as pl

    ldf = pl.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]}).lazy()

    result = polars_dot_to_mermaid(ldf._ldf.to_dot(optimized=True))
    assert result == 'graph TD\n\tp1["TABLE\nπ */2"]'


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.xfail(reason="TODO: skipping since upstream broken this test")
def test_polars_dot_to_mermaid_complex() -> None:
    import polars as pl

    ldf = (
        pl.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})
        .lazy()
        .filter(pl.col("A") > 1)
        .select(pl.col("A"), pl.col("B").alias("B_renamed"))
        .join(pl.DataFrame({"A": [1]}).lazy(), on="A")
    )

    assert (
        polars_dot_to_mermaid(ldf._ldf.to_dot(optimized=True))
        == """graph TD
\tp4["TABLE\nπ 2/2"]
\tp3["FILTER BY [(col(#quot;A#quot;)) > (1)]"]
\tp2["π 2/2"]
\tp5["TABLE\nπ */1"]
\tp1["JOIN INNER\nleft: [col(#quot;A#quot;)];\nright: [col(#quot;A#quot;)]"]
\tp1 --- p2
\tp2 --- p3
\tp3 --- p4
\tp1 --- p5"""
    )


def test_polars_dot_to_mermaid_handles_urls() -> None:
    assert (
        polars_dot_to_mermaid("""graph polars_query {
  p1[label="Check [https://example.com] for more"]
}""")
        == """graph TD
\tp1[\"Check [<a href='https://example.com'>https://example.com</a>] for more\"]"""
    )


def test_as_html_basic_types() -> None:
    """Test as_html with basic Python types."""
    register_formatters()

    # String
    result = as_html("hello world")
    assert result.text == "<span>hello world</span>"

    # Integer
    result = as_html(42)
    assert result.text == "<span>42</span>"

    # Float
    result = as_html(3.14)
    assert result.text == "<span>3.14</span>"

    # Boolean
    result = as_html(True)
    assert result.text == "<span>True</span>"

    # None
    result = as_html(None)
    assert result.text == "<span>None</span>"

    # List
    result = as_html([1, 2, 3])
    assert (
        result.text
        == "<marimo-json-output data-json-data='[1, 2, 3]' data-value-types='&quot;python&quot;'></marimo-json-output>"
    )

    # Dict
    result = as_html({"key": "value"})
    assert "<marimo-json" in result.text


def test_as_html_with_html_object() -> None:
    """Test as_html when passed an Html object - should return it unchanged."""
    from marimo._output.hypertext import Html

    html_obj = Html("<h1>Hello</h1>")
    result = as_html(html_obj)

    # Should return the same object
    assert result is html_obj
    assert result.text == "<h1>Hello</h1>"


def test_as_html_with_repr_html() -> None:
    """Test as_html with objects that have _repr_html_ method."""
    register_formatters()

    class CustomHTML:
        def _repr_html_(self):
            return "<div>Custom HTML content</div>"

    obj = CustomHTML()
    result = as_html(obj)
    assert result.text == "<div>Custom HTML content</div>"


def test_as_html_with_repr_markdown() -> None:
    """Test as_html with objects that have _repr_markdown_ method."""
    register_formatters()

    class CustomMarkdown:
        def _repr_markdown_(self):
            return "# Markdown Title"

    obj = CustomMarkdown()
    result = as_html(obj)
    assert '<span class="markdown prose dark:prose-invert">' in result.text
    assert '<h1 id="markdown-title">Markdown Title</h1>' in result.text


def test_as_html_with_repr_json() -> None:
    """Test as_html with objects that have _repr_json_ method."""
    register_formatters()

    class CustomJSON:
        def _repr_json_(self):
            import json

            return json.dumps({"message": "Hello, World!", "count": 42})

    obj = CustomJSON()
    result = as_html(obj)
    assert "<marimo-json" in result.text


def test_as_html_with_repr_svg() -> None:
    """Test as_html with objects that have _repr_svg_ method."""
    register_formatters()

    class CustomSVG:
        def _repr_svg_(self):
            return '<svg width="100" height="100"><circle cx="50" cy="50" r="40"/></svg>'

    obj = CustomSVG()
    result = as_html(obj)
    assert (
        result.text
        == '<svg width="100" height="100"><circle cx="50" cy="50" r="40"/></svg>'
    )


def test_as_html_with_repr_png() -> None:
    """Test as_html with objects that have _repr_png_ method."""
    register_formatters()

    class CustomPNG:
        def _repr_png_(self):
            return (
                "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABaElEQVR42mNk"
            )

    obj = CustomPNG()
    result = as_html(obj)
    assert (
        '<img src="iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABaElEQVR42mNk" alt="" />'
        in result.text
    )


def test_as_html_with_repr_jpeg() -> None:
    """Test as_html with objects that have _repr_jpeg_ method."""
    register_formatters()

    class CustomJPEG:
        def _repr_jpeg_(self):
            return (
                "/9j/4AAQSkZJRgABAQEAYABgAAD/4QBoRXhpZgAATU0AKgAAAAgAA1IBAAAB"
            )

    obj = CustomJPEG()
    result = as_html(obj)
    assert (
        '<img src="/9j/4AAQSkZJRgABAQEAYABgAAD/4QBoRXhpZgAATU0AKgAAAAgAA1IBAAAB" alt="" />'
        in result.text
    )


def test_as_html_with_plain_wrapper() -> None:
    """Test as_html with Plain wrapper to bypass opinionated formatting."""
    register_formatters()

    # Test with a list that would normally get JSON formatting
    plain_list = Plain([1, 2, 3])
    result = as_html(plain_list)
    assert (
        result.text
        == "<marimo-json-output data-json-data='[1, 2, 3]' data-value-types='&quot;python&quot;'></marimo-json-output>"
    )

    # Test with a dict that would normally get marimo-json formatting
    plain_dict = Plain({"key": "value"})
    result = as_html(plain_dict)
    assert (
        result.text
        == "<marimo-json-output data-json-data='{&quot;key&quot;: &quot;value&quot;}' data-value-types='&quot;python&quot;'></marimo-json-output>"
    )


def test_as_html_with_no_formatter() -> None:
    """Test as_html with objects that have no registered formatter."""
    register_formatters()

    class NoFormatter:
        def __str__(self):
            return "Custom string representation"

    obj = NoFormatter()
    result = as_html(obj)
    assert result.text == "<span>Custom string representation</span>"


def test_as_html_with_broken_formatter() -> None:
    """Test as_html behavior when formatter raises an exception."""
    register_formatters()

    class BrokenFormatter:
        def _repr_html_(self):
            raise ValueError("Formatter is broken")

        def __str__(self):
            return "fallback string"

    obj = BrokenFormatter()
    # Should fall back gracefully
    with pytest.raises(ValueError):
        as_html(obj)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_as_html_with_dataframes() -> None:
    """Test as_html with pandas and polars DataFrames."""
    register_formatters()

    import pandas as pd
    import polars as pl

    # Pandas DataFrame
    pd_df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
    result = as_html(pd_df)
    assert "<marimo-table" in result.text

    # Polars DataFrame
    pl_df = pl.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
    result = as_html(pl_df)
    assert "<marimo-table" in result.text

    # Polars LazyFrame
    pl_ldf = pl_df.lazy()
    result = as_html(pl_ldf)
    assert "<marimo-mermaid" in result.text


def test_as_html_with_display_protocol() -> None:
    """Test as_html with objects implementing _display_ protocol."""
    register_formatters()

    class DisplayProtocol:
        def _display_(self):
            return "display protocol content"

        def _repr_html_(self):
            return "<h1>Should not be used</h1>"

    obj = DisplayProtocol()
    result = as_html(obj)
    assert result.text == "<span>display protocol content</span>"

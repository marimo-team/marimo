from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.hypertext import (
    Html,
    patch_html_for_non_interactive_output,
)
from marimo._plugins.ui._impl.batch import batch as batch_plugin
from marimo._plugins.ui._impl.input import button
from marimo._plugins.ui._impl.table import table


def test_html_initialization():
    html = Html("<p>Hello, World!</p>")
    assert html.text == "<p>Hello, World!</p>"


def test_html_mime():
    html = Html("<p>Test</p>")
    mime_type, content = html._mime_()
    assert mime_type == "text/html"
    assert content == "<p>Test</p>"

    assert html._serialized_mime_bundle == {
        "mimetype": "text/html",
        "data": "<p>Test</p>",
    }


def test_html_mime_with_script():
    # Test that Html returns text/html even with script tags
    # This is expected behavior - Html is for raw HTML that may include scripts
    html = Html('<p>Test</p><script>console.log("hello")</script>')
    mime_type, content = html._mime_()
    assert mime_type == "text/html"
    assert '<script>console.log("hello")</script>' in content


def test_html_format():
    html = Html("<p>\n  Hello\n</p>")
    assert f"{html}" == "<p> Hello </p>"


def test_html_format_multiline():
    html = Html("""
        <div>
            <p>Hello</p>
            <p>World</p>
        </div>
    """)
    assert f"{html}" == "<div> <p>Hello</p> <p>World</p> </div>"


def test_html_format_nested():
    html = Html("""
        <div>
            <span>
                Text
            </span>
        </div>
    """)
    assert f"{html}" == "<div> <span> Text </span> </div>"


def test_html_format_attributes():
    html = Html("""
        <div class="test"
             id="main">
            Content
        </div>
    """)
    assert f"{html}" == '<div class="test" id="main"> Content </div>'


def test_html_format_empty():
    html = Html("")
    assert f"{html}" == ""


def test_html_format_whitespace():
    html = Html("  <p>  Lots   of    spaces  </p>  ")
    assert f"{html}" == "<p>  Lots   of    spaces  </p>"


def test_html_batch():
    html = Html("Name: {name}")
    batched = html.batch(name=button())
    assert isinstance(batched, batch_plugin)


def test_html_center():
    html = Html("<p>Centered</p>")
    centered = html.center()
    assert "justify-content: center" in centered.text


def test_html_right():
    html = Html("<p>Right</p>")
    right_aligned = html.right()
    assert "justify-content: flex-end" in right_aligned.text


def test_html_left():
    html = Html("<p>Left</p>")
    left_aligned = html.left()
    assert "justify-content: flex-start" in left_aligned.text


def test_html_callout():
    html = Html("<p>Important</p>")
    callout = html.callout(kind="warn")
    assert "marimo-callout" in callout.text
    assert "warn" in callout.text


def test_html_style():
    html = Html("<p>Styled</p>")
    styled = html.style({"color": "red", "font-size": "16px"})
    assert "style=" in styled.text
    assert "color:red" in styled.text
    assert "font-size:16px" in styled.text


# Add more tests as needed for edge cases and other functionalities


def test_html_empty():
    html = Html("")
    assert html.text == ""


def test_html_with_special_characters():
    html = Html("<p>Hello & World</p>")
    assert html.text == "<p>Hello & World</p>"


def test_html_nested_elements():
    html = Html("<div><p>Nested</p></div>")
    assert html.text == "<div><p>Nested</p></div>"


def test_html_multiple_elements():
    html = Html("<p>First</p><p>Second</p>")
    assert html.text == "<p>First</p><p>Second</p>"


def test_html_with_attributes():
    html = Html('<a href="https://example.com">Link</a>')
    assert html.text == '<a href="https://example.com">Link</a>'


def test_html_batch_multiple_inputs():
    html = Html("Name: {name}, Age: {age}")
    batched = html.batch(name=button(), age=button())
    assert isinstance(batched, batch_plugin)


def test_html_style_empty_dict():
    html = Html("<p>No Style</p>")
    styled = html.style({})
    assert styled.text == "<div><p>No Style</p></div>"


def test_html_repr_html():
    html = Html("<p>Hello</p>")
    assert html._repr_html_() == "<p>Hello</p>"


def test_html_patch_for_non_interactive_output():
    class ReprMarkdown(Html):
        def _repr_markdown_(self) -> str:
            return "Hello"

    class ReprPng(Html):
        def _repr_png_(self) -> bytes:
            return b"Hello"

    html = ReprMarkdown("<web-component>Hello</web-component>")
    png = ReprPng("<web-component>Hello</web-component>")

    assert html._mime_() == (
        "text/html",
        "<web-component>Hello</web-component>",
    )
    assert png._mime_() == (
        "text/html",
        "<web-component>Hello</web-component>",
    )
    with patch_html_for_non_interactive_output():
        assert html._mime_() == ("text/markdown", "Hello")
        assert png._mime_() == ("image/png", "Hello")

    assert html._mime_() == (
        "text/html",
        "<web-component>Hello</web-component>",
    )
    assert png._mime_() == (
        "text/html",
        "<web-component>Hello</web-component>",
    )


@pytest.mark.skipif(
    not DependencyManager.polars.has() or not DependencyManager.pandas.has(),
    reason="Pandas and Polars not installed",
)
def test_html_rich_elems():
    tbl = table({"button": button()})
    html = Html(tbl)

    assert isinstance(html._serialized_mime_bundle, dict)
    assert html._serialized_mime_bundle == {
        "mimetype": "text/html",
        "data": tbl,
    }

    import pandas as pd

    df = pd.DataFrame({"button": [button()]})
    html = Html(df)
    # ensure public copy exists
    assert hasattr(html, "serialized_mime_bundle") is True
    assert html.serialized_mime_bundle == {
        "mimetype": "text/html",
        "data": df,
    }

    import polars as pl

    df = pl.DataFrame({"button": button()})
    html = Html(df)
    assert html._serialized_mime_bundle == {
        "mimetype": "text/html",
        "data": df,
    }


def test_nested_md_preserves_multiline_code_blocks():
    """Test that nested mo.md() calls preserve multiline code blocks."""
    from marimo._output.md import _md

    # Create a markdown object with a multiline code block
    inner_md = _md("""
        ```python
        multiline
        text
        ```
    """)

    # Create a nested markdown object that includes the inner one
    outer_md = _md(f"{inner_md}")

    # The nested markdown should preserve the multiline formatting
    # The HTML should contain the newlines in the code block
    assert 'multiline</span>\n<span class="n">text' in outer_md.text
    assert (
        'multiline</span> <span class="n">text' not in outer_md.text
    )  # Should not be flattened


def test_nested_md_format_method():
    """Test that the __format__ method of _md returns markdown text."""
    from marimo._output.md import _md

    # Create a markdown object
    md_obj = _md("""
        ```python
        line1
        line2
        ```
    """)

    # When formatted (e.g., in f-strings), it should return the original markdown
    formatted = f"{md_obj}"
    assert "line1\nline2" in formatted
    assert "line1 line2" not in formatted  # Should not be flattened

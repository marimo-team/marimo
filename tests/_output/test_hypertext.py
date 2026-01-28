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
    """Test that the __format__ method of _md returns rendered HTML without flattening."""
    from marimo._output.md import _md

    # Create a markdown object with a code block
    md_obj = _md("""
        ```python
        line1
        line2
        ```
    """)

    # When formatted (e.g., in f-strings), it should return rendered HTML
    # with newlines preserved (not flattened like Html.__format__)
    formatted = f"{md_obj}"

    # Should contain both lines
    assert "line1" in formatted
    assert "line2" in formatted

    # Newlines should be preserved in the HTML (not flattened to spaces)
    # The HTML contains syntax highlighting, so we check the structure
    assert (
        "line1 line2" not in formatted
    )  # Should not be flattened to single line

    # Should be rendered HTML, not raw markdown
    assert "<span" in formatted or "<pre" in formatted or "<code" in formatted


def test_md_format_returns_html_not_markdown():
    """Test that _md.__format__ returns rendered HTML, not raw markdown."""
    from marimo._output.md import _md

    md_obj = _md("**bold** and *italic*")
    formatted = f"{md_obj}"

    # Should be HTML, not raw markdown
    assert "<strong>bold</strong>" in formatted or "<b>bold</b>" in formatted
    assert "**bold**" not in formatted  # Raw markdown should not appear


def test_md_inside_html():
    """Test that mo.md can be embedded inside mo.Html correctly."""
    from marimo._output.hypertext import Html
    from marimo._output.md import _md

    # Create markdown with a code block
    inner_md = _md("""
        ```python
        def hello():
            return "world"
        ```
    """)

    # Embed in Html
    outer_html = Html(f"<div class='wrapper'>{inner_md}</div>")

    # The rendered markdown HTML should be embedded
    assert "<div class='wrapper'>" in outer_html.text

    # Content should be present (syntax highlighting splits keywords into spans)
    assert "def" in outer_html.text
    assert "hello" in outer_html.text
    assert "return" in outer_html.text
    assert "world" in outer_html.text

    # Should have code block structure (pre/code tags)
    assert "<pre>" in outer_html.text or "<code>" in outer_html.text


def test_html_inside_md():
    """Test that mo.Html can be embedded inside mo.md."""
    from marimo._output.hypertext import Html
    from marimo._output.md import _md

    # Create an Html component
    inner_html = Html("<span style='color: red'>Red text</span>")

    # Embed in markdown
    outer_md = _md(f"Some text: {inner_html}")

    # The HTML should be present (possibly flattened by Html.__format__)
    assert "Red text" in outer_md.text


def test_deeply_nested_md():
    """Test multiple levels of mo.md nesting.

    Note: When using indented f-strings, the markdown parser may treat
    the content as a code block due to 4-space indentation. Use non-indented
    strings or cleandoc for nested markdown.
    """
    from marimo._output.md import _md

    # Level 1 - use cleandoc-style (no leading indent in content)
    level1 = _md("""
```python
x = 1
```
""")

    # Level 2 - non-indented to avoid code block interpretation
    level2 = _md(f"""## Code Example

{level1}
""")

    # Level 3
    level3 = _md(f"""# Documentation

{level2}
""")

    # All content should be present
    assert "Documentation" in level3.text
    # Note: "Code Example" becomes an h2 tag
    assert "Code" in level3.text
    assert "Example" in level3.text
    # The variable x and value 1 should be present (possibly in separate spans)
    assert "x" in level3.text
    assert "1" in level3.text


def test_md_with_multiple_code_blocks_nested():
    """Test nesting markdown with multiple code blocks.

    Note: Use non-indented f-strings to avoid markdown treating
    indented content as code blocks.
    """
    from marimo._output.md import _md

    code1 = _md("""
```python
def foo():
    pass
```
""")

    code2 = _md("""
```javascript
function bar() {}
```
""")

    # Non-indented to avoid code block interpretation
    combined = _md(f"""## Python

{code1}

## JavaScript

{code2}
""")

    # Both code blocks should be present (keywords may be split by span tags)
    assert "def" in combined.text
    assert "foo" in combined.text
    assert "function" in combined.text
    assert "bar" in combined.text


def test_md_format_vs_html_format():
    """Test that _md.__format__ behaves differently from Html.__format__."""
    from marimo._output.hypertext import Html
    from marimo._output.md import _md

    # Html flattens content
    html_obj = Html("<div>\n  <p>Hello</p>\n</div>")
    html_formatted = f"{html_obj}"
    assert html_formatted == "<div> <p>Hello</p> </div>"  # Flattened

    # _md preserves structure
    md_obj = _md("""
        ```
        line1
        line2
        ```
    """)
    md_formatted = f"{md_obj}"
    # Should not be flattened - newlines preserved
    assert "line1 line2" not in md_formatted


def test_md_inside_html_with_styling():
    """Test mo.md inside mo.Html with CSS styling."""
    from marimo._output.hypertext import Html
    from marimo._output.md import _md

    inner_md = _md("**Important:** This is *critical*")

    outer_html = Html(f"""
        <div style="background: #f0f0f0; padding: 10px;">
            {inner_md}
        </div>
    """)

    # Should contain the styled wrapper and rendered markdown
    assert 'style="background: #f0f0f0; padding: 10px;"' in outer_html.text
    assert "Important" in outer_html.text


def test_empty_md_format():
    """Test formatting empty markdown."""
    from marimo._output.md import _md

    md_obj = _md("")
    formatted = f"{md_obj}"
    # Should not raise, should return empty or minimal HTML
    assert isinstance(formatted, str)


def test_md_with_inline_code_nested():
    """Test nesting markdown with inline code."""
    from marimo._output.md import _md

    inner = _md("Use `print()` to output")
    outer = _md(f"Tip: {inner}")

    # Inline code should be rendered
    assert "print()" in outer.text
    assert "<code>" in outer.text or "codehilite" in outer.text.lower()

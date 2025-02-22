from __future__ import annotations

from marimo._output.hypertext import (
    Html,
    _js,
    patch_html_for_non_interactive_output,
)
from marimo._plugins.ui._impl.batch import batch as batch_plugin
from marimo._plugins.ui._impl.input import button


def test_html_initialization():
    html = Html("<p>Hello, World!</p>")
    assert html.text == "<p>Hello, World!</p>"


def test_html_mime():
    html = Html("<p>Test</p>")
    mime_type, content = html._mime_()
    assert mime_type == "text/html"
    assert content == "<p>Test</p>"


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


def test_js():
    js_html = _js("console.log('Hello');")
    assert js_html.text == "<script>console.log('Hello');</script>"


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


def test_js_empty():
    js_html = _js("")
    assert js_html.text == "<script></script>"


def test_js_multiple_lines():
    js_code = """
    console.log('Line 1');
    console.log('Line 2');
    """
    js_html = _js(js_code)
    assert "<script>" in js_html.text
    assert "console.log('Line 1');" in js_html.text
    assert "console.log('Line 2');" in js_html.text
    assert "</script>" in js_html.text


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

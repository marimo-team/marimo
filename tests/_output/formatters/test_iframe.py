from __future__ import annotations

from marimo._output.formatters.iframe import (
    _has_script_tag_without_src,
    maybe_wrap_in_iframe,
)


def test_maybe_wrap_in_iframe_no_script():
    html = "<div>Hello world</div>"
    assert maybe_wrap_in_iframe(html) == html


def test_maybe_wrap_in_iframe_with_script_src():
    html = '<script src="foo.js"></script>'
    assert maybe_wrap_in_iframe(html) == html


def test_maybe_wrap_in_iframe_with_inline_script():
    html = '<script>console.log("hello")</script>'
    assert (
        maybe_wrap_in_iframe(html)
        == "<iframe srcdoc='&lt;script&gt;console.log(&quot;hello&quot;)&lt;/script&gt;' width='100%' height='400px' onload='__resizeIframe(this)' frameborder='0'></iframe>"
    )


def test_has_script_tag_without_src_no_script():
    html = "<div>Hello world</div>"
    assert not _has_script_tag_without_src(html)


def test_has_script_tag_without_src_with_src():
    html = '<script src="foo.js"></script>'
    assert not _has_script_tag_without_src(html)


def test_has_script_tag_without_src_inline():
    html = '<script>console.log("hello")</script>'
    assert _has_script_tag_without_src(html)


def test_has_script_tag_without_src_multiple():
    html = """
        <script src="foo.js"></script>
        <div>Some content</div>
        <script>console.log("hello")</script>
    """
    assert _has_script_tag_without_src(html)


def test_has_script_tag_without_src_with_attributes():
    html = '<script type="text/javascript" defer>alert("hi")</script>'
    assert _has_script_tag_without_src(html)

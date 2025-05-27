from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from marimo._output.md import _md, latex

if TYPE_CHECKING:
    from pathlib import Path


def test_md() -> None:
    # Test basic markdown conversion
    input_text = "This is **bold** and this is _italic_."
    expected_output = '<span class="markdown prose dark:prose-invert"><span class="paragraph">This is <strong>bold</strong> and this is <em>italic</em>.</span></span>'  # noqa: E501
    assert _md(input_text).text == expected_output

    # Test disabling markdown class
    expected_output_no_class = '<span class="paragraph">This is <strong>bold</strong> and this is <em>italic</em>.</span>'  # noqa: E501
    assert (
        _md(input_text, apply_markdown_class=False).text
        == expected_output_no_class
    )


# def test_md_size() -> None:
#     input_text = "This is **bold** and this is _italic_."
#     expected_output = '<span class="markdown prose dark:prose-invert prose-lg"><span class="paragraph">This is <strong>bold</strong> and this is <em>italic</em>.</span></span>'  # noqa: E501
#     assert _md(input_text, size="lg").text == expected_output


def test_md_code_blocks() -> None:
    # Test code block conversion
    code_input = "```python\nprint('Hello, world!')\n```"
    expected_output = '<div class="language-python codehilite"><pre><span></span><code><span class="nb">print</span><span class="p">(</span><span class="s1">&#39;Hello, world!&#39;</span><span class="p">)</span>\n</code></pre></div>'  # noqa: E501
    assert _md(code_input, apply_markdown_class=False).text == expected_output


def test_md_latex() -> None:
    # Test inline LaTeX
    inline_latex = "Here is an inline equation $||(E=mc^2||)$"
    expected_inline = '<span class="paragraph">Here is an inline equation <marimo-tex class="arithmatex">||(||(E=mc^2||)||)</marimo-tex></span>'
    assert (
        _md(inline_latex, apply_markdown_class=False).text == expected_inline
    )

    # Test display LaTeX
    display_latex = "Here is a display equation:\n\n||[\nE = mc^2\n||]"
    expected_display = '<span class="paragraph">Here is a display equation:</span>\n<span class="paragraph">||[\nE = mc^2\n||]</span>'
    assert (
        _md(display_latex, apply_markdown_class=False).text == expected_display
    )

    # Test multiple LaTeX expressions
    multiple_latex = (
        "Equation 1: ||(a^2 + b^2 = c^2||) and equation 2: ||(E=mc^2||)"
    )
    expected_multiple = '<span class="paragraph">Equation 1: ||(a^2 + b^2 = c^2||) and equation 2: ||(E=mc^2||)</span>'
    assert (
        _md(multiple_latex, apply_markdown_class=False).text
        == expected_multiple
    )

    # Test LaTeX with markdown formatting
    mixed_latex = "**Bold** ||(x^2||) and _italic_ ||[y = mx + b||]"
    expected_mixed = '<span class="paragraph"><strong>Bold</strong> ||(x^2||) and <em>italic</em> ||[y = mx + b||]</span>'
    assert _md(mixed_latex, apply_markdown_class=False).text == expected_mixed


def test_md_links() -> None:
    # Test external link conversion
    link_input = "[Google](https://google.com)"
    expected_output = '<span class="paragraph"><a href="https://google.com" rel="noopener" target="_blank">Google</a></span>'  # noqa: E501
    assert _md(link_input, apply_markdown_class=False).text == (
        expected_output
    )


def test_md_footnotes() -> None:
    # Test footnote conversion
    footnote_input = (
        "Here is a footnote reference[^1].\n\n[^1]: Here is the footnote."
    )
    expected_output = '<span class="paragraph">Here is a footnote reference<sup id="fnref:2-1"><a class="footnote-ref" href="#fn:2-1">1</a></sup>.</span>\n<div class="footnote">\n<hr />\n<ol>\n<li id="fn:2-1">\n<span class="paragraph">Here is the footnote.&#160;<a class="footnote-backref" href="#fnref:2-1" title="Jump back to footnote 1 in the text">&#8617;</a></span>\n</li>\n</ol>\n</div>'  # noqa: E501
    assert _md(footnote_input, apply_markdown_class=False).text == (
        expected_output
    )


def test_md_iconify() -> None:
    # Test iconify conversion
    iconify_input = "This is an icon: ::lucide:user::"
    expected_output = '<span class="paragraph">This is an icon: <iconify-icon icon="lucide:user" inline=""></iconify-icon></span>'  # noqa: E501
    assert (
        _md(iconify_input, apply_markdown_class=False).text == expected_output
    )

    # Test multiple icons
    multiple_icons_input = "Icons: ::mdi:home:: ::fa:car:: ::lucide:settings::"
    expected_output = '<span class="paragraph">Icons: <iconify-icon icon="mdi:home" inline=""></iconify-icon> <iconify-icon icon="fa:car" inline=""></iconify-icon> <iconify-icon icon="lucide:settings" inline=""></iconify-icon></span>'  # noqa: E501
    assert (
        _md(multiple_icons_input, apply_markdown_class=False).text
        == expected_output
    )

    # Test icon within other markdown elements
    mixed_input = "# Header with ::lucide:star:: icon\n\n**Bold text with ::mdi:alert:: icon**"  # noqa: E501
    expected_output = '<h1 id="header-with-icon">Header with <iconify-icon icon="lucide:star" inline=""></iconify-icon> icon</h1>\n<span class="paragraph"><strong>Bold text with <iconify-icon icon="mdi:alert" inline=""></iconify-icon> icon</strong></span>'  # noqa: E501
    assert _md(mixed_input, apply_markdown_class=False).text == expected_output


def test_md_sane_lists() -> None:
    input_text = "2. hey\n3. hey"
    expected_output = '<ol start="2">\n<li>hey</li>\n<li>hey</li>\n</ol>'
    assert _md(input_text, apply_markdown_class=False).text == expected_output


def test_md_pycon_detection() -> None:
    # Test basic pycon detection with >>> prompts
    pycon_input = """```
>>> print("Hello, world!")
Hello, world!
>>> x = 42
>>> print(x)
42
```"""
    result = _md(pycon_input, apply_markdown_class=False).text
    assert "language-pycon" in result
    assert "&gt;&gt;&gt;" in result  # HTML-encoded >>>

    # Test pycon detection with continuation prompts
    pycon_continuation = """```
>>> def hello():
...     print("Hello")
...     return True
>>> hello()
Hello
True
```"""
    result = _md(pycon_continuation, apply_markdown_class=False).text
    assert "language-pycon" in result
    assert "&gt;&gt;&gt;" in result  # HTML-encoded >>>

    # Test mixed prompts
    mixed_prompts = """```
>>> import os
>>> for i in range(2):
...     print(i)
0
1
>>> print("done")
done
```"""
    result = _md(mixed_prompts, apply_markdown_class=False).text
    assert "language-pycon" in result

    # Test that regular python code is not converted
    regular_python = """```python
def hello():
    print("Hello")
    return True

hello()
```"""
    result = _md(regular_python, apply_markdown_class=False).text
    assert "language-python" in result
    assert "language-pycon" not in result

    # Test that code without language is converted if it has pycon patterns
    no_language_pycon = """```
>>> 1 + 1
2
>>> "hello".upper()
'HELLO'
```"""
    result = _md(no_language_pycon, apply_markdown_class=False).text
    assert "language-pycon" in result

    # Test that code without prompts is not converted
    no_prompts = """```
print("Hello")
x = 42
print(x)
```"""
    result = _md(no_prompts, apply_markdown_class=False).text
    assert "language-pycon" not in result

    # Test edge case: low ratio of prompts (should not convert)
    low_ratio = """```
>>> print("one line with prompt")
line without prompt
another line without prompt
yet another line without prompt
and another line without prompt
```"""
    result = _md(low_ratio, apply_markdown_class=False).text
    # Should not be converted because prompt ratio is too low (1/5 = 20% < 30%)
    assert "language-pycon" not in result

    # Test edge case: high ratio of prompts (should convert)
    high_ratio = """```
>>> print("first")
first
>>> print("second")
second
>>> print("third")
third
some output
```"""
    result = _md(high_ratio, apply_markdown_class=False).text
    # Should be converted because prompt ratio is high (3/7 = ~43% > 30%)
    assert "language-pycon" in result

    # Test empty code block
    empty_block = """```
```"""
    result = _md(empty_block, apply_markdown_class=False).text
    assert "language-pycon" not in result

    # Test with specified language other than python (should not convert)
    other_language = """```javascript
>>> this is not python
console.log("hello");
```"""
    result = _md(other_language, apply_markdown_class=False).text
    assert "language-javascript" in result
    assert "language-pycon" not in result

    # Test with whitespace around prompts
    whitespace_prompts = """```
   >>> print("with spaces")
   with spaces
   >>> x = 1
```"""
    result = _md(whitespace_prompts, apply_markdown_class=False).text
    assert "language-pycon" in result

    # Test single line with prompt (should convert)
    single_line = """```
>>> print("single")
```"""
    result = _md(single_line, apply_markdown_class=False).text
    assert "language-pycon" in result

    # Test only continuation prompts (should convert)
    only_continuation = """```
... print("continuation")
... print("more")
```"""
    result = _md(only_continuation, apply_markdown_class=False).text
    assert "language-pycon" in result


def test_md_repr_markdown():
    input_text = "This is **bold** and this is _italic_."
    md = _md(input_text)
    assert md._repr_markdown_() == input_text


@patch("marimo._runtime.output")
def test_latex_via_path(output: MagicMock, tmp_path: Path) -> None:
    filename = tmp_path / "macros.tex"
    filename.write_text("\\newcommand{\\\foo}{bar}")
    latex(filename=filename)
    assert (
        output.append.call_args[0][0].text
        == '<span class="markdown prose dark:prose-invert"><marimo-tex class="arithmatex">||[\n\\newcommand{\\\x0coo}{bar}\n||]</marimo-tex></span>'
    )


@patch("marimo._runtime.output")
@patch("marimo._output.md.urlopen")
def test_latex_via_url(mock_urlopen: MagicMock, output: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.read.return_value = b"\\newcommand{\\\foo}{bar}"
    mock_urlopen.return_value.__enter__.return_value = mock_response

    latex(filename="https://example.com/macros.tex")
    assert (
        output.append.call_args[0][0].text
        == '<span class="markdown prose dark:prose-invert"><marimo-tex class="arithmatex">||[\n\\newcommand{\\\foo}{bar}\n||]</marimo-tex></span>'
    )

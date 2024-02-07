from marimo._utils.rst_to_html import convert_rst_to_html


def test_basic_conversion() -> None:
    rst_content = "**bold text**"
    expected_html = (
        '<div class="document">\n<p><strong>bold text</strong></p>\n</div>\n'
    )
    result = convert_rst_to_html(rst_content)
    assert result.strip() == expected_html.strip()


def test_empty_input() -> None:
    rst_content = ""
    expected_html = '<div class="document">\n</div>\n'
    result = convert_rst_to_html(rst_content)
    assert result.strip() == expected_html.strip()


def test_code_block() -> None:
    rst_content = "```python\nprint('Hello, world!')\n```"
    expected_html = (
        '<div class="document">\n<p><tt class="docutils literal">`python\n'
        '<span class="pre">print(\'Hello,</span> <span class="pre">world!\')'
        "</span>\n`</tt></p>\n</div>"
    )
    result = convert_rst_to_html(rst_content)
    assert result.strip() == expected_html.strip()

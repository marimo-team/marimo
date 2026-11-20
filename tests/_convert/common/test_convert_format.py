from __future__ import annotations

import re
from textwrap import dedent

import pytest

from marimo._ast import codegen
from marimo._ast.cell import CellConfig
from marimo._ast.compiler import compile_cell, extract_markdown
from marimo._convert.common import format


def test_markdown_to_marimo():
    markdown = "# Hello, World!\nThis is a test."
    expected = 'mo.md(r"""\n# Hello, World!\nThis is a test.\n""")'
    assert format.markdown_to_marimo(markdown) == expected

    markdown = 'Here are some quotes: """'
    expected = "mo.md(r'''\nHere are some quotes: \"\"\"\n''')"

    assert format.markdown_to_marimo(markdown) == expected

    markdown = r"This has a backslash: \\"
    expected = '''
mo.md(r"""
This has a backslash: \\\\
""")'''.strip()
    assert format.markdown_to_marimo(markdown) == expected


def test_markdown_to_marimo_with_quotes():
    markdown = '"this is markdown"'
    expected = (
        '''\
mo.md(r"""
"this is markdown"
""")'''
    ).strip()
    assert format.markdown_to_marimo(markdown) == expected


@pytest.mark.parametrize(
    "markdown",
    [
        '```python\ndef f():\n    """Docstring."""\n```',
        'say """hi"""',
        r"Write \"\"\" to escape '''",
    ],
)
def test_markdown_to_marimo_roundtrips_quotes(markdown: str) -> None:
    assert extract_markdown(format.markdown_to_marimo(markdown)) == markdown


@pytest.mark.parametrize("prefix", ["", "f"])
@pytest.mark.parametrize("markdown", ['say """hi"""', r'Write \""" to escape'])
def test_markdown_to_marimo_non_raw_roundtrips(
    markdown: str, prefix: str
) -> None:
    code = format.markdown_to_marimo(markdown, prefix)
    assert extract_markdown(code) == markdown


def test_markdown_to_marimo_non_raw_uses_frontend_escape() -> None:
    # The editor only reverses `\"""`
    code = format.markdown_to_marimo('say """hi"""', "")
    assert code == 'mo.md("""\nsay \\"""hi\\"""\n""")'


def test_generate_from_sources():
    # Test with basic sources
    sources = ["print('Hello')", "x = 5"]
    result = codegen.generate_filecontents(
        codes=sources,
        names=["_", "_"],
        cell_configs=[CellConfig(), CellConfig()],
    )
    result = re.sub(r"__generated_with = .*", "", result)

    assert result == dedent(
        """
import marimo


app = marimo.App()


@app.cell
def _():
    print('Hello')


@app.cell
def _():
    x = 5


if __name__ == "__main__":
    app.run()
      """.lstrip()
    )


def test_generate_from_sources_with_cell_configs():
    sources = ["print('Hello')", "x = 5"]
    cell_configs = [CellConfig(hide_code=True), CellConfig(hide_code=False)]
    result = codegen.generate_filecontents(
        codes=sources,
        names=["_", "_"],
        cell_configs=cell_configs,
    )
    result = re.sub(r"__generated_with = .*", "", result)
    assert result == dedent(
        """
import marimo


app = marimo.App()


@app.cell(hide_code=True)
def _():
    print('Hello')


@app.cell
def _():
    x = 5


if __name__ == "__main__":
    app.run()
        """.lstrip()
    )


def test_markdown_with_quotes_and_cell_configs():
    """Test that markdown ending in double quotes works with cell configs.

    Regression test for issue #6741 where markdown cells ending in double
    quotes failed to convert when cell configs were non-default.
    """
    # Simulate a markdown cell ending in double quotes that can't be parsed
    markdown_code = 'mo.md("Marimo is the best")'
    sources = [markdown_code]
    cell_configs = [CellConfig(hide_code=True)]

    # This should not raise AttributeError
    result = codegen.generate_filecontents(
        codes=sources,
        names=["_"],
        cell_configs=cell_configs,
    )

    # Verify the result contains the expected config
    assert "hide_code=True" in result
    # Verify the markdown content is properly escaped
    assert (
        r"mo.md(\"Marimo is the best\")" in result
        or "Marimo is the best" in result
    )


def test_get_markdown_from_cell_base():
    empty_markdown_str = "mo.md('hello')"
    markdown = format.get_markdown_from_cell(
        compile_cell(empty_markdown_str, "id"), empty_markdown_str
    )
    assert markdown == "hello"


def test_get_markdown_from_cell_empty():
    empty_markdown_str = "mo.md()"
    markdown = format.get_markdown_from_cell(
        compile_cell(empty_markdown_str, "id"), empty_markdown_str
    )
    assert markdown is None


def test_get_markdown_from_cell_keeps_authored_backslash():
    code = 'mo.md(r"""\n\\"""quote\n""")'
    markdown = format.get_markdown_from_cell(compile_cell(code, "id"), code)
    assert markdown == '\\"""quote'


def test_get_markdown_from_cell_broken():
    empty_markdown_str = "mo.md()"
    # This can occur because the cell isn't recompiled at this point.
    markdown = format.get_markdown_from_cell(
        compile_cell(empty_markdown_str, "id"), "mo.md(f'{broken(}')"
    )
    assert markdown is None

from __future__ import annotations

import re
from textwrap import dedent

from marimo._ast import codegen
from marimo._ast.cell import CellConfig
from marimo._ast.compiler import compile_cell
from marimo._convert import utils


def test_markdown_to_marimo():
    markdown = "# Hello, World!\nThis is a test."
    expected = 'mo.md(r"""\n# Hello, World!\nThis is a test.\n""")'  # noqa: E501
    assert utils.markdown_to_marimo(markdown) == expected

    markdown = 'Here are some quotes: """'
    expected = r'''
mo.md(r"""
Here are some quotes: \"\"\"
""")'''.strip()

    assert utils.markdown_to_marimo(markdown) == expected

    markdown = r"This has a backslash: \\"
    expected = '''
mo.md(r"""
This has a backslash: \\\\
""")'''.strip()  # noqa: E501
    assert utils.markdown_to_marimo(markdown) == expected


def test_markdown_to_marimo_with_quotes():
    markdown = '"this is markdown"'
    expected = (
        '''\
mo.md(r"""
"this is markdown"
""")'''
    ).strip()
    assert utils.markdown_to_marimo(markdown) == expected


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
    return


@app.cell
def _():
    x = 5
    return


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
    return


@app.cell
def _():
    x = 5
    return


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
    markdown = utils.get_markdown_from_cell(
        compile_cell(empty_markdown_str, "id"), empty_markdown_str
    )
    assert markdown == "hello"


def test_get_markdown_from_cell_empty():
    empty_markdown_str = "mo.md()"
    markdown = utils.get_markdown_from_cell(
        compile_cell(empty_markdown_str, "id"), empty_markdown_str
    )
    assert markdown is None


def test_get_markdown_from_cell_broken():
    empty_markdown_str = "mo.md()"
    # This can occur because the cell isn't recompiled at this point.
    markdown = utils.get_markdown_from_cell(
        compile_cell(empty_markdown_str, "id"), "mo.md(f'{broken(}')"
    )
    assert markdown is None

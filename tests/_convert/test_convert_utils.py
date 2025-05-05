from __future__ import annotations

import re
from textwrap import dedent

from marimo._ast.cell import CellConfig
from marimo._convert import utils


def test_markdown_to_marimo():
    markdown = "# Hello, World!\nThis is a test."
    expected = 'mo.md(\n    r"""\n    # Hello, World!\n    This is a test.\n    """\n)'  # noqa: E501
    assert utils.markdown_to_marimo(markdown) == expected

    markdown = 'Here are some quotes: """'
    expected = (
        'mo.md(\n    r"""\n    Here are some quotes: \\"\\"\\"\n    """\n)'  # noqa: E501
    )
    assert utils.markdown_to_marimo(markdown) == expected

    markdown = r"This has a backslash: \\"
    expected = 'mo.md(\n    r"""\n    This has a backslash: \\\\\n    """\n)'  # noqa: E501
    assert utils.markdown_to_marimo(markdown) == expected


def test_generate_from_sources():
    # Test with basic sources
    sources = ["print('Hello')", "x = 5"]
    result = utils.generate_from_sources(sources=sources)
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
    result = utils.generate_from_sources(
        sources=sources, cell_configs=cell_configs
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

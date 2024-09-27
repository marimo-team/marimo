from __future__ import annotations

from textwrap import dedent

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
    result = utils.generate_from_sources(sources)

    assert result == dedent(
        """
import marimo

__generated_with = "0.8.20"
app = marimo.App()


@app.cell
def __():
    print('Hello')
    return


@app.cell
def __():
    x = 5
    return (x,)


if __name__ == "__main__":
    app.run()
      """.lstrip()
    )

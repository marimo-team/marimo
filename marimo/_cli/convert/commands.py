# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path

import click

from marimo._cli.convert.ipynb import convert_from_ipynb
from marimo._cli.convert.markdown import convert_from_md
from marimo._cli.convert.utils import load_external_file


@click.argument("filename", required=True)
def convert(
    filename: str,
) -> None:
    r"""Convert a Jupyter notebook or Markdown file to a marimo notebook.

    The argument may be either a path to a local .ipynb/.md file,
    or an .ipynb/.md file hosted on GitHub.

    Example usage:

        marimo convert your_nb.ipynb > your_nb.py

    or

        marimo convert your_nb.md > your_nb.py

    Jupyter notebook conversion will strip out all outputs. Markdown cell
    conversion with occur on the presence of `\`\`\`{python}` code blocks.
    After conversion, you can open the notebook in the editor:

        marimo edit your_nb.py

    Since marimo is different from traditional notebooks, once in the editor,
    you may need to fix errors like multiple definition errors or cycle
    errors.
    """
    ext = Path(filename).suffix
    if ext not in (".ipynb", ".md", ".qmd"):
        raise click.UsageError("File must be an .ipynb or .md file")

    text = load_external_file(filename, ext)
    if ext == ".ipynb":
        notebook = convert_from_ipynb(text)
    else:
        assert ext in (".md", ".qmd")
        notebook = convert_from_md(text)
    click.echo(notebook)

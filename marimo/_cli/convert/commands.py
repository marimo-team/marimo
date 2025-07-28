# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from marimo._cli.convert.utils import load_external_file
from marimo._cli.print import echo
from marimo._cli.utils import prompt_to_overwrite
from marimo._convert.converters import MarimoConvert
from marimo._utils.paths import maybe_make_dirs


@click.argument("filename", required=True)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Output file to save the converted notebook to. "
        "If not provided, the converted notebook will be printed to stdout."
    ),
)
def convert(
    filename: str,
    output: Optional[Path],
) -> None:
    r"""Convert a Jupyter notebook, Markdown file, or unknown Python script to a marimo notebook.

    The argument may be either a path to a local .ipynb/.md/.py file,
    or an .ipynb/.md file hosted on GitHub.

    Example usage:

        marimo convert your_nb.ipynb -o your_nb.py

    or

        marimo convert your_nb.md -o your_nb.py

    or

        marimo convert script.py -o your_nb.py

    Jupyter notebook conversion will strip out all outputs. Markdown cell
    conversion will occur on the presence of `{python}` code fences.

    For .py files:
    - If the file is already a valid marimo notebook, no conversion is performed
    - Unknown Python scripts are converted by preserving the header (docstrings/comments)
      and splitting the code into cells, with __main__ blocks separated

    After conversion, you can open the notebook in the editor:

        marimo edit your_nb.py

    Since marimo is different from traditional notebooks, once in the editor,
    you may need to fix errors like multiple definition errors or cycle
    errors.
    """

    ext = Path(filename).suffix
    if ext not in (".ipynb", ".md", ".qmd", ".py"):
        raise click.UsageError("File must be an .ipynb, .md, or .py file")

    text = load_external_file(filename, ext)
    if ext == ".ipynb":
        notebook = MarimoConvert.from_ipynb(text).to_py()
    elif ext in (".md", ".qmd"):
        notebook = MarimoConvert.from_md(text).to_py()
    else:
        assert ext == ".py"
        # First check if it's already a valid marimo notebook
        from marimo._ast.parse import parse_notebook

        try:
            parsed = parse_notebook(text)
        except SyntaxError:
            # File has syntax errors
            echo("File cannot be converted. It may have syntax errors.")
            return

        if parsed and parsed.valid:
            # Already a valid marimo notebook
            echo("File is already a valid marimo notebook.")
            return

        # Check if it has the violation indicating it's an unknown Python script
        if parsed and any(
            v.description == "Unknown content beyond header"
            for v in parsed.violations
        ):
            try:
                notebook = MarimoConvert.from_non_marimo_py_script(
                    text
                ).to_py()
            except ImportError as e:
                # Check if jupytext is the missing module in the cause chain
                if (
                    e.__cause__
                    and getattr(e.__cause__, "name", None) == "jupytext"
                ):
                    from marimo._cli.print import green

                    raise click.ClickException(
                        f"{e}\n\n"
                        f"  {green('Tip:')} If you're using uv, run:\n\n"
                        f"    uvx --with=jupytext marimo convert {filename}"
                    ) from e
                raise
        else:
            # File has other issues (syntax errors, etc.)
            echo("File cannot be converted. It may have syntax errors.")
            return

    if output:
        output_path = Path(output)
        if prompt_to_overwrite(output_path):
            # Make dirs if needed
            maybe_make_dirs(output)
            Path(output).write_text(notebook, encoding="utf-8")
            echo(f"Converted notebook saved to {output}")
    else:
        echo(notebook)

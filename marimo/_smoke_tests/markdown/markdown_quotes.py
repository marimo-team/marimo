# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md("""Markdown""")
    return


@app.cell
def _(mo):
    mo.md(r"""Markdown with an escaped \"""quote\"""!!""")
    return


@app.cell
def _(mo):
    mo.md(
        """
        Markdown with a trailing "quote"
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        "Markdown" with a leading quote
        """
    )
    return


@app.cell
def _(mo):
    mo.md("""Markdown with a trailing 'single quote'""")
    return


@app.cell
def _(mo):
    mo.md("""'Markdown' with a leading single quote""")
    return


@app.cell
def _(mo):
    mo.md("""Markdown with an triple-single '''quote'''!!""")
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

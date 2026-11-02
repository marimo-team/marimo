# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md("""
    Markdown
    """)


@app.cell
def _(mo):
    mo.md(r"""
    Markdown with an escaped \"""quote\"""!!
    """)


@app.cell
def _(mo):
    mo.md("""
    Markdown with a trailing "quote"
    """)


@app.cell
def _(mo):
    mo.md("""
    "Markdown" with a leading quote
    """)


@app.cell
def _(mo):
    mo.md("""
    Markdown with a trailing 'single quote'
    """)


@app.cell
def _(mo):
    mo.md("""
    'Markdown' with a leading single quote
    """)


@app.cell
def _(mo):
    mo.md("""
    Markdown with an triple-single '''quote'''!!
    """)


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()

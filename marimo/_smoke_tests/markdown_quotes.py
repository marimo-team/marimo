# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.9"
app = marimo.App(width="medium")


@app.cell
def __(mo):
    mo.md("""Markdown""")
    return


@app.cell
def __(mo):
    mo.md(r"""Markdown with an escaped \"""quote\"""!!""")
    return


@app.cell
def __(mo):
    mo.md(
        """
        Markdown with a trailing "quote"
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        """
        "Markdown" with a leading quote
        """
    )
    return


@app.cell
def __(mo):
    mo.md("""Markdown with a trailing 'single quote'""")
    return


@app.cell
def __(mo):
    mo.md("""'Markdown' with a leading single quote""")
    return


@app.cell
def __(mo):
    mo.md("""Markdown with an triple-single '''quote'''!!""")
    return


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()

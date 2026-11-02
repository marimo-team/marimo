# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Heading 1
    """)


@app.cell
def _(mo):
    mo.carousel([mo.md("# Carousel Heading")])


@app.cell
def _(mo):
    mo.md("""
    # Heading 2

    Headings between carousel and tabs are detected
    """)


@app.cell
def _(mo):
    mo.ui.tabs({"Tab 1": mo.md("# Tabs Heading")})


@app.cell
def _(mo):
    mo.md("""
    # Heading 3

    Headings between tabs and accordion are detected
    """)


@app.cell
def _(mo):
    mo.accordion({"Accordion 1": mo.md("# Accordion Heading")})


@app.cell
def _(mo):
    mo.md("""
    # Heading 4
    """)


if __name__ == "__main__":
    app.run()

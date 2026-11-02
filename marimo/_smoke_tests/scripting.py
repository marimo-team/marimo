# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    hello
    """)


@app.cell
def _(mo):
    mo.Html("<script>console.log(document.querySelectorAll('p')[0].textContent)</script>")


if __name__ == "__main__":
    app.run()

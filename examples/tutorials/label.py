# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.13"
app = marimo.App(width="medium")


@app.cell
def __(mo, t):
    mo.md(
        rf"""
        Hello

        {t}
        """
    )
    return


@app.cell
def __(mo):
    mo.ui.button(label="submit $x$")
    return


@app.cell
def __(mo):
    t = mo.ui.text(label="label")
    return t,


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()

# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md(
        """
        # Tooltips

        <span data-tooltip="Hello world!">Hover me</span>
        """
    )
    return


@app.cell
def _(mo):
    mo.ui.button(label="<span data-tooltip='I said dont press'>Don't press</span>")
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()

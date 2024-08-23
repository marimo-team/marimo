# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.8.0"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md(
        """
        # Tooltips 

        <span data-tooltip="Hello world!">Hover me</span>
        """
    )
    return


@app.cell
def __(mo):
    mo.ui.button(label="<span data-tooltip='I said dont press'>Don't press</span>")
    return


@app.cell
def __():
    return


if __name__ == "__main__":
    app.run()

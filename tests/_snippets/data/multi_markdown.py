# Copyright 2026 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Multi Markdown Snippet

        This is the title cell with a description.
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        This is a second markdown cell that should also be rendered.
        """
    )
    return


@app.cell
def __():
    x = 1 + 1
    return (x,)


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()

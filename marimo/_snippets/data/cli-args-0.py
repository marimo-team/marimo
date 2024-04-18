# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.4.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # CLI Arguments: Reading CLI arguments

        Use `mo.cli_args` to access command line arguments passed to the notebook.
        For example, you can pass arguments to the notebook when running it as an
        application with `marimo run`.

        ```bash
        marimo run app.py -- --arg1 value1 --arg2 value2
        ```
        """
    )
    return


@app.cell
def __(mo):
    params = mo.cli_args()
    params
    return params,


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()

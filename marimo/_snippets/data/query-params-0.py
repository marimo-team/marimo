# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.4.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Query Parameters: Reading query parameters

        Use `mo.query_params` to access query parameters passed to the notebook.
        """
    )
    return


@app.cell
def __(mo):
    params = mo.query_params()
    print(params)
    return (params,)


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()

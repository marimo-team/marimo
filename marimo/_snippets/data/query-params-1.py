# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.4.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Query Parameters: Writing to query parameters

        You can also use `mo.query_params` to set query parameters in order
        to keep track of state in the URL. This is useful for bookmarking
        or sharing a particular state of the notebook while running as an
        application with `marimo run`.
        """
    )
    return


@app.cell
def __(mo):
    query_params = mo.query_params()
    return query_params,


@app.cell
def __(mo, query_params):
    slider = mo.ui.slider(
        0,
        10,
        value=query_params.get("slider") or 1,
        on_change=lambda x: query_params.set("slider", x),
    )
    slider
    return slider,


@app.cell
def __(mo, query_params):
    search = mo.ui.text(
        value=query_params.get("search") or "",
        on_change=lambda x: query_params.set("search", x),
    )
    search
    return search,


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()

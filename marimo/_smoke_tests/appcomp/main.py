# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    from inner import app

    return (app,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Render the same app multiple times
    """)


@app.cell
async def _(app):
    result = await app.embed()
    result.output
    return (result,)


@app.cell
def _(result):
    result.defs["x"].value


@app.cell
def _(result):
    result.defs["y"].value


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Clone an app
    """)


@app.cell
def _(app):
    clone = app.clone()
    return (clone,)


@app.cell
async def _(clone):
    clone_result = await clone.embed()
    clone_result.output


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Parametrize an app
    """)


@app.cell
def _(app):
    parametrized_app = app.clone()
    return (parametrized_app,)


@app.cell
async def _(parametrized_app):
    _result = await parametrized_app.embed(defs={"x_initial_value": 0})
    _result.output


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Render an app inside tabs
    """)


@app.cell
async def _(app, mo):
    tabs = mo.ui.tabs({"🧮": (await app.embed()).output, "📝": mo.md("Hello world")})
    tabs


@app.cell
def _(mo):
    mo.md(rf"""
    ## Render an app that uses function calls
    """)


@app.cell
def _():
    from make_table import app as table_app

    return (table_app,)


@app.cell
async def _(table_app):
    table_app_results = await table_app.embed()
    return (table_app_results,)


@app.cell
def _(table_app_results):
    table_app_results.output


@app.cell
def _(table_app_results):
    table_app_results.defs


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()

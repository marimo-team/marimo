# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.6.26"
app = marimo.App(width="medium")


@app.cell
def __():
    from inner import app
    return app,


@app.cell(hide_code=True)
def __(mo):
    mo.md("## Render the same app multiple times")
    return


@app.cell
async def __(app):
    result = await app.embed()
    result.output
    return result,


@app.cell
def __(result):
    result.defs["x"].value
    return


@app.cell
def __(result):
    result.defs["y"].value
    return


@app.cell
def __(mo):
    mo.md("## Render an app inside tabs")
    return


@app.cell
async def __(app, mo):
    tabs = mo.ui.tabs({"🧮": (await app.embed()).output, "📝": mo.md("Hello world")})
    tabs
    return tabs,


@app.cell
def __(mo):
    mo.md(rf"## Render an app that uses function calls")
    return


@app.cell
def __():
    from make_table import app as table_app
    return table_app,


@app.cell
async def __(table_app):
    table_app_results = await table_app.embed()
    return table_app_results,


@app.cell
def __(table_app_results):
    table_app_results.output
    return


@app.cell
def __(table_app_results):
    table_app_results.defs
    return


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()

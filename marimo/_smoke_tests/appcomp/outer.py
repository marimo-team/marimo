# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.6.22"
app = marimo.App()


@app.cell
def __():
    from inner import app
    return app,


@app.cell(hide_code=True)
def __(mo):
    mo.md("## Render the same app multiple times")
    return


@app.cell
def __(app):
    app
    return


@app.cell
def __(app):
    app
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("## Render an app inside tabs")
    return


@app.cell
def __(app, mo):
    tabs = mo.ui.tabs({"🧮": app, "📝": mo.md("Hello world")}); tabs
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
def __(table_app):
    table_app
    return


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()

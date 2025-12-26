# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    from inner import app
    return (app,)


@app.cell
def _(mo):
    mo.md("# middle")
    return


@app.cell
def _(mo, result):
    x_plus_y = result.defs['x'].value + result.defs['y'].value
    mo.md(f"The middle app has calculated `x_plus_y` ... try retrieving it")
    return


@app.cell
async def _(app):
    result = await app.embed()
    result.output
    return (result,)


if __name__ == "__main__":
    app.run()

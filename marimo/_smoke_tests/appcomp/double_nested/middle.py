# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.26"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    from inner import app
    return app,


@app.cell
def __(mo):
    mo.md("# middle")
    return


@app.cell
def __(mo, result):
    x_plus_y = result.defs['x'].value + result.defs['y'].value
    mo.md(f"The middle app has calculated `x_plus_y` ... try retrieving it")
    return x_plus_y,


@app.cell
async def __(app):
    result = await app.embed()
    result.output
    return result,


if __name__ == "__main__":
    app.run()

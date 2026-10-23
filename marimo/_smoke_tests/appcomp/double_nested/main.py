# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell
def _():
    from middle import app as middle

    return (middle,)


@app.cell
async def _(middle):
    result = await middle.embed()
    result.output
    return (result,)


@app.cell
def _(result):
    result.defs["x_plus_y"]
    return


if __name__ == "__main__":
    app.run()

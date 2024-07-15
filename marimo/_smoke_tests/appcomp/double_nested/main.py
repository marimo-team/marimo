# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.6.26"
app = marimo.App(width="medium")


@app.cell
def __():
    from middle import app as middle
    return middle,


@app.cell
async def __(middle):
    result = await middle.embed()
    result.output
    return result,


@app.cell
def __(result):
    result.defs["x_plus_y"]
    return


if __name__ == "__main__":
    app.run()

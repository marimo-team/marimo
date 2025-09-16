# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    from imperative_output import app
    return (app,)


@app.cell
def _():
    import marimo as mo
    return


@app.cell
async def _(app):
    (await app.embed()).output
    return


if __name__ == "__main__":
    app.run()

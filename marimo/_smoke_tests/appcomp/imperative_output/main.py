# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    from imperative_output import app

    return (app,)


@app.cell
def _():
    import marimo as mo


@app.cell
async def _(app):
    (await app.embed()).output


if __name__ == "__main__":
    app.run()

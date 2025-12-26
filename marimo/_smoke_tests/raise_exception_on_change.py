# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.function
def error(v):
    raise ValueError(str(v))


@app.cell
def _(mo):
    s = mo.ui.slider(1, 10, on_change=lambda v: error(v))
    s
    return


if __name__ == "__main__":
    app.run()

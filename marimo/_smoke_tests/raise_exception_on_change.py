# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.5"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    def error(v):
        raise ValueError(str(v))
    return error,


@app.cell
def __(error, mo):
    s = mo.ui.slider(1, 10, on_change=lambda v: error(v))
    s
    return s,


if __name__ == "__main__":
    app.run()

# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.12"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    v = mo.ui.number(value=0, start=-10, stop=10)
    v
    return v,


@app.cell
def __(v):
    v.value
    return


if __name__ == "__main__":
    app.run()

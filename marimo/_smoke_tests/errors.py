# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(y):
    x = y
    return x,


@app.cell
def __(z):
    y = z
    return y,


@app.cell
def __(x):
    z = x
    c = 0
    return c, z


@app.cell
def __(b):
    a = 0
    del b
    c = 0
    return a, c


app._unparsable_cell(
    r"""
    a =
    """,
    name="__"
)


@app.cell
def __():
    a = 1
    b = 0
    c = 0
    return a, b, c


if __name__ == "__main__":
    app.run()

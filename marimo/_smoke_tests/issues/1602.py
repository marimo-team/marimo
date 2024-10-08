# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.17"
app = marimo.App(width="medium")


@app.cell
def __():
    class Boom:
        def __getattr__(self, _):
            return ...
    return Boom,


@app.cell
def __(Boom):
    b = Boom()
    return b,


@app.cell
def __(b):
    callable(b.__dataframe__)
    return


if __name__ == "__main__":
    app.run()

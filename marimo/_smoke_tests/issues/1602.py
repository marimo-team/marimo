# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.class_definition
class Boom:
    def __getattr__(self, _):
        return ...


@app.cell
def _():
    b = Boom()
    return (b,)


@app.cell
def _(b: Boom):
    callable(b.__dataframe__)


if __name__ == "__main__":
    app.run()

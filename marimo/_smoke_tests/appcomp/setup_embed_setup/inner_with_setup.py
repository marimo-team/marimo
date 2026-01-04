# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


with app.setup:
    import marimo as mo


@app.cell
def _():
    inner_value = 42
    mo.md("# Inner App with Setup Cell")
    return (inner_value,)


@app.cell
def _(inner_value):
    mo.md(f"Inner value is: {inner_value}")
    return


if __name__ == "__main__":
    app.run()

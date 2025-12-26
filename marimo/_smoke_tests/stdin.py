# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    value = input("what is your name?")
    return (value,)


@app.cell
def _(mo, value):
    mo.md(f"## 👋 Hi {value}")
    return


@app.cell
def _():
    print('hi')
    return


@app.cell
def _():
    print('there')
    return


if __name__ == "__main__":
    app.run()

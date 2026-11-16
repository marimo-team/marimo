# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
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
def _(mo, value: str):
    mo.md(f"## 👋 Hi {value}")


@app.cell
def _():
    print('hi')


@app.cell
def _():
    print('there')


if __name__ == "__main__":
    app.run()

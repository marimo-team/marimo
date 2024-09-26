# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.77"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    value = input("what is your name?")
    return value,


@app.cell
def __(mo, value):
    mo.md(f"## 👋 Hi {value}")
    return


@app.cell
def __():
    print('hi')
    return


@app.cell
def __():
    print('there')
    return


if __name__ == "__main__":
    app.run()

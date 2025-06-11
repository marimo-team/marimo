# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.13.15"
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
    mo.md(f"""## 👋 Hi {value}""")
    return


if __name__ == "__main__":
    app.run()

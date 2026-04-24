# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo>=0.23.2",
# ]
# ///

import marimo

__generated_with = "0.23.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    x = 42
    x
    return (x,)


@app.cell
def _():
    "hello from a string"
    return


@app.cell
def _(x):
    result = x * 2
    result
    return (result,)


@app.cell
def _(mo):
    mo.md("""
    ## This is markdown

    With **bold** and *italic* text.
    """)
    return


@app.cell
def _(mo, result, x):
    mo.md(f"The value of x is **{x}** and result is **{result}**")
    return


@app.cell
def _():
    data = {"name": "Alice", "age": 30, "scores": [95, 87, 92]}
    data
    return


@app.cell
def _(mo):
    mo.Html("<div style='padding:20px;background:#eef;border-radius:8px'><b>Raw HTML block</b><br>This should render.</div>")
    return


if __name__ == "__main__":
    app.run()

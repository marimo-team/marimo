import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""
    ## Basic
    """)


@app.cell
def _(mo):
    mo.ui.number()


@app.cell
def _(mo):
    mo.ui.number(-10, 10)


@app.cell
def _(mo):
    mo.md(r"""
    ## Edge cases
    """)


@app.cell
def _(mo):
    # Above max safe int
    BAD_INT = 999999999999999990
    v = mo.ui.number(
        value=BAD_INT, start=BAD_INT - 5, stop=BAD_INT + 5, full_width=True
    )
    v
    return (v,)


@app.cell
def _(v):
    v.value


@app.cell
def _(mo):
    def on_change(new_value):
        print(new_value)


    mo.ui.number(start=-1e255, stop=1e255, value=5, on_change=on_change)
    return (on_change,)


@app.cell
def _(mo, on_change):
    import numpy as np

    # Cannot set infinity as range
    mo.ui.number(start=-np.inf, stop=np.inf, value=5, on_change=on_change)


if __name__ == "__main__":
    app.run()

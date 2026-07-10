# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "matplotlib==3.10.1",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Use local variables

    Variables prefixed with an underscore are local to a cell, and can be redefined.
    """)
    return


@app.cell
def _():
    for _i in range(3):
        print(_i)
    return


@app.cell
def _():
    for _i in range(4, 6):
        print(_i)
    return


@app.cell
def _():
    # _i is not defined in this cell
    _i
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Wrap code in functions

    Wrap cells in functions to minimize the number of temporary globals you introduce.
    """)
    return


@app.cell
def _():
    import matplotlib.pyplot as plt

    return (plt,)


@app.cell
def _(plt):
    def _():
        fig, ax = plt.subplots()
        plt.plot([1, 2])
        return ax

    _()
    return


if __name__ == "__main__":
    app.run()

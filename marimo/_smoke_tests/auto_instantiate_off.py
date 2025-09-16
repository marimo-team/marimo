import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""If you run this first, then this should run and the `import marimo` cell should run, but nothing else""")
    return


@app.cell
def _():
    # If you run this first, then this should run, but not `y = x + 1`
    x = 2
    x
    return (x,)


@app.cell
def _(x):
    # If you run this first, then this should run and `x = 2`
    y = x + 2
    y
    return


if __name__ == "__main__":
    app.run()

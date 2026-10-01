import marimo

__generated_with = "0.0.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    x = 1
    return (x,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # This cell is hidden
    """)
    return


@app.cell(disabled=True)
def _(x):
    y = x + 1
    return (y,)


@app.cell
def _(y):
    print(y)
    return


@app.cell(expand_output=True)
def _(y):
    z = y + 1
    return


if __name__ == "__main__":
    app.run()

import marimo

__generated_with = "0.12.9"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    t = mo.ui.date()
    n = mo.ui.slider(1, 10)
    return n, t


@app.cell
def _(mo, n, t):
    mo.hstack([t, n], justify="start")
    return


@app.cell
def _(mo, n, t):
    mo.vstack([t, n])
    return


if __name__ == "__main__":
    app.run()

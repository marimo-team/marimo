import marimo

__generated_with = "0.23.2"
app = marimo.App()


@app.cell
def _(y):
    x = y
    return (x,)


@app.cell
def _():
    Y = 0  # noqa: N806
    return (Y,)


@app.cell
def _(z):
    Z = z  # noqa: N806
    return


@app.cell
def _():
    z = 1 / 0
    return (z,)


@app.cell
def _(Y, x):
    y = x
    y = Y  # noqa: F841
    return (y,)


if __name__ == "__main__":
    app.run()

import marimo

__generated_with = "0.15.2"
app = marimo.App()


@app.cell
def _(z):
    x = 1 + z  # This should trigger MR002 - cycle dependency
    return (x,)


@app.cell
def _(x):
    y = x + 1
    return (y,)


@app.cell
def _(y):
    z = y + 1
    return (z,)


if __name__ == "__main__":
    app.run()

import marimo

__generated_with = "0.23.2"
app = marimo.App()


@app.cell
def _():
    x = 1
    return (x,)


@app.cell
def _(x):
    y = x + 1
    return (y,)


@app.cell
def _(y):
    z = y + 1
    return


if __name__ == "__main__":
    app.run()

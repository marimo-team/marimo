import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    mo.stop(True, "Stopped early")
    return (mo,)


@app.cell
def _():
    x = 10
    return (x,)


@app.cell
def _(x):
    y = x + 1
    return (y,)


if __name__ == "__main__":
    app.run()

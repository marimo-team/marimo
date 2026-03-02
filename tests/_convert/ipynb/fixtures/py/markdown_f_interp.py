import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    x = 42
    return (x,)


@app.cell
def _(mo, x):
    mo.md(f"The value is **{x}**")
    return


if __name__ == "__main__":
    app.run()

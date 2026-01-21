import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Hello, World!
    """)
    return


@app.cell
def _():
    x = 1
    y = 2
    z = x + y
    return (z,)


@app.cell
def _(z):
    print(z)
    return


if __name__ == "__main__":
    app.run()

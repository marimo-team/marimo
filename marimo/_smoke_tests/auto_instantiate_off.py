import marimo

__generated_with = "0.9.34"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __(mo):
    mo.md(r"""If you run this first, then this should run and the `import marimo` cell should run, but nothing else""")
    return


@app.cell
def __():
    # If you run this first, then this should run, but not `y = x + 1`
    x = 2
    x
    return (x,)


@app.cell
def __(x):
    # If you run this first, then this should run and `x = 2`
    y = x + 2
    y
    return (y,)


if __name__ == "__main__":
    app.run()

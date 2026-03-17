import marimo

__generated_with = "0.19.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    title = mo.md("# Hello World")
    return (title,)


@app.cell
def _(mo, title):
    mo.vstack([
        title,
        mo.md("This should display above this text."),
    ])
    return


if __name__ == "__main__":
    app.run()

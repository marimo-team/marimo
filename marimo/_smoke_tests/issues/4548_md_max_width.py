

import marimo

__generated_with = "0.12.9"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    md = mo.md(
        "> long text goes here long text goes here long text goes here long text goes here long text goes here long text goes here long text goes here long text goes here long text goes here long text goes here long text goes here long text goes here long text goes here long text goes here"
    )
    md
    return md, mo


@app.cell
def _(md, mo):
    mo.vstack([md])
    return


@app.cell
def _(md, mo):
    mo.vstack([mo.hstack([md])])
    return


if __name__ == "__main__":
    app.run()

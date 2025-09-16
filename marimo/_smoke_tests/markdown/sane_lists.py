import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(
        """
        2. hey
        2. hey
        2. hey
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        1. hey
        1. hey
        1. hey
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        1. hey
        2. hey
        2. hey
        """
    )
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

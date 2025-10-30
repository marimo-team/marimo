import marimo

__generated_with = "0.17.4"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md("""
    r"""Markdown cell with error"""
    """)
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()

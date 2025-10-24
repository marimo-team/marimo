import marimo

__generated_with = "0.17.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md(
    r"""
        # Test Markdown
    Already indented text.
    """
    )
    return


@app.cell
def _(mo):
    mo.md(
        rf"""
        Another markdown cell with indentation.

        Some **bold** text and _italic_ text.
    """
    )
    return


@app.cell
def _(mo):
    mo.md(
            rf"""single line""")
    return

@app.cell
def _(mo):
    mo.md(
    fr"""single line""")
    return

@app.cell
def _(mo):
    mo.md(fr"siiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiingle line")
    return

if __name__ == "__main__":
    app.run()

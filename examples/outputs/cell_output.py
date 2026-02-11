import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _(mo):
    mo.md("""
    The last expression of a cell is its visual output. This output
    appears above the cell when editing a notebook, with notebook code
    serving as a "caption" for the output. Outputs can be configured
    to appear below cells in the user settings.

    If running
    a notebook as an app, the output is the visual representation
    of the cell (code is hidden by default).
    """)
    return


@app.cell
def _():
    "Hello, world!"
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()

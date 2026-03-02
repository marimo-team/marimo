import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # This cell is hidden
    """)
    return


@app.cell
def _():
    x = 1
    return


if __name__ == "__main__":
    app.run()

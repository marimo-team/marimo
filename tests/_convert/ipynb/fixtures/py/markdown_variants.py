import marimo

__generated_with = "0.0.0"
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
def _(mo):
    mo.md("""
    # No prefix

    Plain triple-quoted markdown.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    # R-prefix

    Raw triple-quoted markdown.
    """)
    return


@app.cell
def _(mo):
    mo.md(f"""
    # F-prefix

    F-string with no interpolation.
    """)
    return


@app.cell
def _(mo):
    mo.md(fr"""
    # FR-prefix

    FR-string with no interpolation.
    """)
    return


@app.cell
def _(mo, x):
    mo.md(f"The value is **{x}**")
    return


if __name__ == "__main__":
    app.run()

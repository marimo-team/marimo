import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Use **admonitions** in markdown to bring attention to text. Here are some examples.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    /// admonition | Heads up.

    Here's some information.
    ///
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    /// attention | Attention!

    This is important.
    ///
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()

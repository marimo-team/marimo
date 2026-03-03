import marimo

__generated_with = "0.19.10"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    hello $$f(x) = y$$ world
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    hello
    $$f(x) = y$$
    world
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    hello $$this is not latex

    $$ this is still not latex
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()

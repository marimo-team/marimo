import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    # Register globals
    mo.latex(filename=mo.notebook_dir() / "macros.tex")
    return (mo,)


@app.cell
def _(mo):
    mo.md(r"""
    $$
    c = \pm\root{a^2 + b^2}\in\RR
    $$
    """)


@app.cell
def _(mo):
    mo.md(r"""
    $c = \pm\root{a^2 + b^2}\in\RR$
    """)


if __name__ == "__main__":
    app.run()

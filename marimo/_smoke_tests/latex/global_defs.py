import marimo

__generated_with = "0.11.3"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    # Register globals
    mo.latex(filename=mo.notebook_dir() / "macros.tex")
    return (mo,)


@app.cell
def _(mo):
    mo.md(
        r"""
        $$
        c = \pm\root{a^2 + b^2}\in\RR
        $$
        """
    )
    return


@app.cell
def _(mo):
    mo.md(r"""$c = \pm\root{a^2 + b^2}\in\RR$""")
    return


if __name__ == "__main__":
    app.run()

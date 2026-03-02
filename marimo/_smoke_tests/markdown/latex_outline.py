import marimo

__generated_with = "0.20.2"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Introduction

    This notebook tests that LaTeX renders correctly in the outline panel.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The equation $E = mc^2$

    Einstein's famous mass-energy equivalence.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Inline math: $\alpha + \beta = \gamma$

    Greek letters in a heading.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Display math

    $$\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}$$
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Mixed: text and $\sum_{i=1}^{n} x_i$

    A heading with both plain text and a summation.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Plain heading (no LaTeX)

    This heading has no math for comparison.
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()

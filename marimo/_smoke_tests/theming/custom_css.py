# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "vega-datasets",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.13.10"
app = marimo.App(width="medium", css_file="custom.css")


@app.cell
def _():
    import marimo as mo
    from vega_datasets import data
    return data, mo


@app.cell
def _(data):
    data.cars()
    return


@app.cell
def _(mo):
    mo.callout(
        mo.md("""
    ## Callout

    This font should be styled
    """)
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
    # heading

    Here is a paragraph
    """
    )
    return


@app.cell
def _(mo):
    # This text should be aligned-right
    mo.ui.number(value=50)
    return


if __name__ == "__main__":
    app.run()

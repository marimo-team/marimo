# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "vega-datasets",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium", html_head_file="head.html")


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


if __name__ == "__main__":
    app.run()

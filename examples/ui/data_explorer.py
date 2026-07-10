# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "polars==1.17.1",
#     "vega-datasets==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from vega_datasets import data

    return (data,)


@app.cell
def _(data, mo):
    explorer = mo.ui.data_explorer(data.iris())
    explorer
    return (explorer,)


@app.cell
def _(explorer):
    explorer.value
    return


if __name__ == "__main__":
    app.run()

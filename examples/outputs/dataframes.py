# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "vega-datasets==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from vega_datasets import data

    return (data,)


@app.cell
def _(data):
    df = data.cars()
    return (df,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    marimo has a rich dataframe viewer built-in:

    - built-in global search
    - per-column sorting and filtering
    - per-column histograms
    - download filtered views
    - paginate through the whole dataframe
    """)
    return


@app.cell
def _(df):
    df
    return


if __name__ == "__main__":
    app.run()

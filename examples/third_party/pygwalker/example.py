# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pygwalker==0.4.9.13",
#     "vega-datasets==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import pygwalker as pyg

    from vega_datasets import data

    return data, pyg


@app.cell
def _(data, pyg):
    df = data.iris()

    pyg.walk(df)
    return


if __name__ == "__main__":
    app.run()

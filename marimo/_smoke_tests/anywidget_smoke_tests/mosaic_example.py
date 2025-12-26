# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "mosaic-widget",
#     "marimo",
#     "pyyaml",
#     "quak==0.3.2",
#     "polars==1.33.1",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.16.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd
    import marimo as mo
    import os
    import yaml

    dir_path = os.path.dirname(os.path.realpath(__file__))


    from mosaic_widget import MosaicWidget

    weather = pd.read_csv(
        "https://uwdata.github.io/mosaic-datasets/data/seattle-weather.csv",
        parse_dates=["date"],
    )

    # Load weather spec, remove data key to ensure load from Pandas
    with open(dir_path + "/weather.yaml") as f:
        spec = yaml.safe_load(f)
        spec.pop("data")

    w = mo.ui.anywidget(MosaicWidget(spec, data={"weather": weather}))
    return (w,)


@app.cell
def _(w):
    w
    return


@app.cell
def _(w):
    w.value
    return


@app.cell
def _():
    import quak
    return (quak,)


@app.cell
def _(quak):
    import polars as pl

    _df = pl.read_parquet("https://github.com/uwdata/mosaic/raw/main/data/athletes.parquet")
    quak.Widget(_df)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()

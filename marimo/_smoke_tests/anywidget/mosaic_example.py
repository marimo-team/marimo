# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "mosaic-widget",
#     "marimo",
#     "pyyaml",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.2"
app = marimo.App(width="medium")


@app.cell
def __(__file__):
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
    return MosaicWidget, dir_path, f, mo, os, pd, spec, w, weather, yaml


@app.cell
def __(w):
    w
    return


if __name__ == "__main__":
    app.run()

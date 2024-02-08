# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.2.2"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        """
    # HoloViews in marimo
    ```
    pip install holoviews
    ```
    """
    )
    return


@app.cell
def __():
    import pandas as pd
    import numpy as np
    import holoviews as hv
    from holoviews import opts
    import marimo as mo

    hv.extension("bokeh", "plotly", "matplotlib")
    return hv, mo, np, opts, pd


@app.cell
def __(pd):
    station_info = pd.read_csv(
        "https://raw.githubusercontent.com/holoviz/holoviews/main/examples/assets/station_info.csv"
    )
    return station_info,


@app.cell
def __(hv, mo):
    backend = mo.ui.dropdown(
        options=list(hv.extension._backends.keys()),
        label="Choose your backend",
        full_width=True,
    )
    return backend,


@app.cell
def __(backend, hv, mo, station_info):
    scatter = hv.Scatter(station_info, "services", "ridership")
    if backend.value:
        hv.extension(backend.value)
    mo.hstack([backend, scatter], align="center")
    return scatter,


@app.cell
def __(mo):
    mo.md("## Area chart")
    return


@app.cell
def __(hv, np):
    xs = np.linspace(0, np.pi * 4, 40)
    hv.Area((xs, np.sin(xs)))
    return xs,


@app.cell
def __(mo):
    mo.md("## Scatter chart")
    return


@app.cell
def __(scatter):
    scatter
    return


@app.cell
def __(mo):
    mo.md("# HV Plot")
    return


@app.cell
def __():
    import hvplot.pandas
    from bokeh.sampledata.penguins import data as df

    df.hvplot.scatter(x='bill_length_mm', y='bill_depth_mm', by='species')
    return df, hvplot


if __name__ == "__main__":
    app.run()

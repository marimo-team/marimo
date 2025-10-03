# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "numpy",
#     "holoviews",
#     "pandas",
#     "marimo",
#     "hvplot",
#     "bokeh",
#     "polars",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _(mo):
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
def _():
    import pandas as pd
    import numpy as np
    import holoviews as hv
    from holoviews import opts
    import marimo as mo

    hv.extension("bokeh", "plotly", "matplotlib")
    return hv, mo, np, pd


@app.cell
def _(pd):
    station_info = pd.read_csv(
        "https://raw.githubusercontent.com/holoviz/holoviews/main/examples/assets/station_info.csv"
    )
    return (station_info,)


@app.cell
def _(hv, mo):
    backend = mo.ui.dropdown(
        options=list(hv.extension._backends.keys()),
        label="Choose your backend",
        full_width=True,
    )
    return (backend,)


@app.cell
def _(backend, hv, mo, station_info):
    scatter = hv.Scatter(station_info, "services", "ridership")
    if backend.value:
        hv.extension(backend.value)
    mo.hstack([backend, scatter], align="center")
    return (scatter,)


@app.cell
def _(mo):
    mo.md("""## Area chart""")
    return


@app.cell
def _(hv, np):
    xs = np.linspace(0, np.pi * 4, 40)
    hv.Area((xs, np.sin(xs)))
    return


@app.cell
def _(mo):
    mo.md("""## Scatter chart""")
    return


@app.cell
def _(scatter):
    scatter
    return


@app.cell
def _(mo):
    mo.md("""# HV Plot""")
    return


@app.cell
def _():
    import hvplot.pandas
    from bokeh.sampledata.penguins import data as df

    df.hvplot.scatter(x="bill_length_mm", y="bill_depth_mm", by="species")
    return


@app.cell
def _(mo):
    mo.md("""# Composed Views""")
    return


@app.cell
def _():
    import polars as pl
    from hvplot import polars

    df3 = pl.DataFrame({"x": [1, 2, 3], "y": [1, 2, 3]}, strict=False)
    df4 = pl.DataFrame({"x": [1, 2, 3], "y": [3, 2.5, 3]}, strict=False)
    return df3, df4


@app.cell
def _(df3, df4):
    df3.hvplot.line("x", "y") * df4.hvplot.line("x", "y")
    return


@app.cell
def _(df3, df4):
    df3.hvplot.line("x", "y") + df4.hvplot.line("x", "y")
    return


if __name__ == "__main__":
    app.run()

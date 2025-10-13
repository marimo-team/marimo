# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "holoviews==1.21.0",
#     "hvplot==0.12.1",
#     "netcdf4==1.7.2",
#     "pooch==1.8.2",
#     "xarray==2025.9.0",
# ]
# ///

import marimo

__generated_with = "0.15.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import xarray as xr
    import hvplot.xarray  # noqa: F401
    import holoviews as hv

    hv.extension('bokeh')
    hv.output(widget_location='top')

    air_ds = xr.tutorial.open_dataset('air_temperature').load()
    air_ds.air.hvplot.image()
    return air_ds, hv, xr


@app.cell
def _():
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()

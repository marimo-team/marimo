# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.8.0"
app = marimo.App()


@app.cell
def __(mo):
    themes = ["dark_minimal", "light_minimal", "contrast", "night_sky", "caliber"]
    selected_theme = mo.ui.radio(themes, label="Theme", value="dark_minimal")
    selected_theme
    return selected_theme, themes


@app.cell
def __(selected_theme):
    import polars as pl
    import holoviews as hv
    import hvplot.polars

    hv.extension("bokeh")
    hvplot.extension("bokeh")
    hv.renderer("bokeh").theme = selected_theme.value
    return hv, hvplot, pl


@app.cell
def __(pl):
    df = pl.DataFrame({"a": range(1, 10), "b": range(1, 10)})
    df.plot.line(
        x="a",
        y="b",
    )
    return df,


@app.cell
def __(selected_theme):
    from bokeh.plotting import curdoc, figure

    x = [1, 2, 3, 4, 5]
    y = [6, 7, 6, 4, 5]

    curdoc().theme = selected_theme.value

    p = figure(width=300, height=300)
    p.line(x, y)

    p
    return curdoc, figure, p, x, y


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()

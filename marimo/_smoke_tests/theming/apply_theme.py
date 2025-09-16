# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "seaborn",
#     "matplotlib",
#     "holoviews",
#     "bokeh",
#     "vega-datasets",
#     "altair",
#     "plotly",
#     "marimo",
#     "pandas",
#     "numpy",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.app_meta().theme
    return


@app.cell
def _(mo):
    mo.md(r"""# Seaborn""")
    return


@app.cell
def _(df, plt):
    import seaborn as sns

    plt.figure(figsize=(10, 6))
    sns.lineplot(x="x", y="y", data=df)
    plt.title("Seaborn: Sine Wave")
    return


@app.cell
def _(mo):
    mo.md(r"""# Matplotlib""")
    return


@app.cell
def _(x, y):
    import matplotlib.pyplot as plt

    plt.figure(figsize=(10, 6))
    plt.plot(x, y)
    plt.title("Matplotlib: Sine Wave")
    return (plt,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Holoviews""")
    return


@app.cell
def _(df):
    import holoviews as hv

    hv.extension("bokeh")
    curve = hv.Curve(df, "x", "y")
    hv.render(curve.opts(title="Holoviews: Sine Wave", width=800, height=400))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Bokeh""")
    return


@app.cell
def _(x, y):
    # Bokeh
    from bokeh.plotting import figure, show

    p = figure(
        title="Bokeh: Sine Wave",
        x_axis_label="x",
        y_axis_label="y",
        width=800,
        height=400,
    )
    p.line(x, y, line_width=2)
    p
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Altair""")
    return


@app.cell(hide_code=True)
def _(mo):
    import altair as alt
    from vega_datasets import data

    chart = (
        alt.Chart(data.cars())
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
    )

    chart = mo.ui.altair_chart(chart)
    chart
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Plotly""")
    return


@app.cell(hide_code=True)
def _(df):
    # Plotly
    import plotly.express as px

    px.line(df, x="x", y="y", title="Plotly: Sine Wave")
    return


@app.cell
def _(np, pd):
    # Sample data
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    df = pd.DataFrame({"x": x, "y": y})
    return df, x, y


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import numpy as np
    import pandas as pd
    return np, pd


if __name__ == "__main__":
    app.run()

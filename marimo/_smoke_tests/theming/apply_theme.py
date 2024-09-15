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

__generated_with = "0.8.3"
app = marimo.App(width="medium")


@app.cell
def __(mo):
    mo.app_meta().theme
    return


@app.cell
def __(mo):
    mo.md(r"""# Seaborn""")
    return


@app.cell
def __(df, plt):
    import seaborn as sns

    plt.figure(figsize=(10, 6))
    sns.lineplot(x="x", y="y", data=df)
    plt.title("Seaborn: Sine Wave")
    return (sns,)


@app.cell
def __(mo):
    mo.md(r"""# Matplotlib""")
    return


@app.cell
def __(x, y):
    import matplotlib.pyplot as plt

    plt.figure(figsize=(10, 6))
    plt.plot(x, y)
    plt.title("Matplotlib: Sine Wave")
    return (plt,)


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""# Holoviews""")
    return


@app.cell
def __(df):
    import holoviews as hv

    hv.extension("bokeh")
    curve = hv.Curve(df, "x", "y")
    hv.render(curve.opts(title="Holoviews: Sine Wave", width=800, height=400))
    return curve, hv


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""# Bokeh""")
    return


@app.cell
def __(x, y):
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
    return figure, p, show


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""# Altair""")
    return


@app.cell(hide_code=True)
def __(mo):
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
    return alt, chart, data


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""# Plotly""")
    return


@app.cell(hide_code=True)
def __(df):
    # Plotly
    import plotly.express as px

    px.line(df, x="x", y="y", title="Plotly: Sine Wave")
    return (px,)


@app.cell
def __(np, pd):
    # Sample data
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    df = pd.DataFrame({"x": x, "y": y})
    return df, x, y


@app.cell
def __():
    import marimo as mo

    return (mo,)


@app.cell
def __():
    import numpy as np
    import pandas as pd

    return np, pd


if __name__ == "__main__":
    app.run()

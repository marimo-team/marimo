# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "altair==6.0.0",
#     "marimo",
#     "matplotlib==3.10.8",
#     "numpy==2.4.1",
#     "pandas==2.3.3",
#     "plotly==6.5.2",
#     "pyarrow==22.0.0",
# ]
# ///

import marimo

__generated_with = "0.19.4"
app = marimo.App(width="medium")


@app.cell
def cell_imports():
    import marimo as mo
    import matplotlib.pyplot as plt
    import altair as alt
    import plotly.graph_objs as go
    import numpy as np
    import pandas as pd
    import pyarrow

    np.random.seed(5)
    return alt, go, mo, np, pd, plt


@app.cell
def pure_markdown_cell(mo):
    mo.md("""
    pure markdown cell
    """)
    return


@app.cell
def ends_with_markdown(mo):
    _x = 10
    mo.md("ends with markdown")
    return


@app.cell
def cell_slider(mo):
    slider = mo.ui.slider(0, 10)
    slider
    return


@app.cell
def cell_matplotlib(np, plt):
    # Matplotlib plot
    x = np.linspace(0, 2 * np.pi, 100)
    y = np.sin(x)
    fig, ax = plt.subplots()
    mpplot = ax.plot(x, y)
    fig
    return (fig,)


@app.cell
def basic_dataframe(pd):
    df = pd.DataFrame({"x": [1]})
    df
    return (df,)


@app.cell
def _(df, mo):
    mo.ui.table(df)
    return


@app.cell
def _(df, mo):
    mo.ui.dataframe(df)
    return


@app.cell
def _(fig, mo):
    # Interactive figure
    mo.mpl.interactive(fig)
    return


@app.cell
def cell_altair(alt, pd):
    # Altair chart
    _df = pd.DataFrame({"x": [1], "y": [1]})
    chart = alt.Chart(_df).mark_circle().encode(x="x:O", y="y:Q")
    chart
    return (chart,)


@app.cell
def _(chart, mo):
    # Wrapped in mo.ui.altair_chart()
    mo.ui.altair_chart(chart)
    return


@app.cell
def cell_plotly(go, np):
    # Plotly chart
    trace = go.Scatter(x=np.arange(2), y=np.random.randn(2), mode="lines+markers")
    plot = go.Figure(data=[trace])
    plot
    return (plot,)


@app.cell
def _(mo, plot):
    # Wrapped in mo.ui.plotly
    mo.ui.plotly(plot)
    return


if __name__ == "__main__":
    app.run()

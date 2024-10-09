
#uvx --with plotly --with pandas --with 'marimo==0.9' marimo edit plotly_marimo.py

import marimo

__generated_with = "0.9.1"
app = marimo.App(width="medium")


@app.cell
def __(mo):
    a = mo.ui.checkbox(label="toggle to change data")
    a
    return (a,)


@app.cell
def __(a, np, px):
    x = np.array([1, 2, 3, 4]) if a.value else np.arange(3, 20)
    y = np.sin(x / 5)
    px.scatter(x=x, y=y)
    return x, y


@app.cell
def __(a):
    a
    return


@app.cell
def __(mo, px, x, y):
    plot = mo.ui.plotly(px.scatter(x=x, y=y)); plot
    return (plot,)


@app.cell
def __(plot):
    plot.value
    return


@app.cell
def __():
    import plotly.express as px
    import marimo as mo
    import numpy as np
    return mo, np, px


if __name__ == "__main__":
    app.run()

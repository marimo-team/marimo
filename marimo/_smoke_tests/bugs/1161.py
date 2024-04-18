# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.4.0"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    return


@app.cell
def __(mo):
    slider = mo.ui.slider(1, 5)
    slider
    return slider,


@app.cell
def __(mo, slider):
    import plotly.express as px
    x_data = [1,2,3,4,5,6][:slider.value]
    y_data = [1,2,3,2,3,4][:slider.value]
    fig = px.scatter(x=x_data, y=y_data)

    p = mo.ui.plotly(fig)
    p
    return fig, p, px, x_data, y_data


@app.cell
def __(p):
    p.value
    return


if __name__ == "__main__":
    app.run()

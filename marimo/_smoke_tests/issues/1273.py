# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.4.7"
app = marimo.App(width="full")


@app.cell
def __():
    import marimo as mo
    import plotly.express as px
    return mo, px


@app.cell
def __(mo):
    s = mo.ui.range_slider(start=-5, stop=5, show_value=True, label='x range')
    x, y = list(range(10)), [i * i for i in range(-5, 5)]
    return s, x, y


@app.cell
def __(mo, px, s, x, y):
    # takes affect when using the slider
    mo.vstack([
        s,
        px.scatter(x=x, y=y, range_x=s.value, title=f'range_x: {s.value}')
    ])
    return


@app.cell
def __(mo, px, s, x, y):
    # takes affect when using the slider
    # also is zoom/range is persisted across app view, but reset when the slider changes the range
    plot = mo.ui.plotly(px.scatter(x=x, y=y, range_x=s.value, title=f'range_x: {s.value}'))
    plot
    return plot,


if __name__ == "__main__":
    app.run()

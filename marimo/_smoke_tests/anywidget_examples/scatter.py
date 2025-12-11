# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "jupyter-scatter==0.22.2",
#     "numpy==2.3.5",
# ]
# ///

import marimo

__generated_with = "0.18.3"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import jscatter
    import numpy as np

    x = np.random.rand(500)
    y = np.random.rand(500)

    scatter = jscatter.Scatter(x=x, y=y)
    w = mo.ui.anywidget(scatter.widget)
    w
    return (w,)


@app.cell
def _(w):
    w.selection
    return


@app.cell
def _(w):
    w.hovering
    return


if __name__ == "__main__":
    app.run()

# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
#     "matplotlib==3.9.2",
#     "numpy==1.26.4",
#     "tldraw==3.0.0",
# ]
# ///

import marimo

__generated_with = "0.8.19"
app = marimo.App(width="medium")


@app.cell
def __():
    import matplotlib.pyplot as plt
    import numpy as np
    plt.style.use('_mpl-gallery')

    # make the data
    np.random.seed(3)
    x = 4 + np.random.normal(0, 2, 24)
    y = 4 + np.random.normal(0, 2, len(x))
    # size and color:
    sizes = np.random.uniform(15, 80, len(x))
    opacity = np.random.uniform(0, 1, len(x))
    return np, opacity, plt, sizes, x, y


@app.cell
def __():
    from tldraw import ReactiveColorPicker
    import marimo as mo

    widget = mo.ui.anywidget(ReactiveColorPicker())
    return ReactiveColorPicker, mo, widget


@app.cell
def __(mo, np, opacity, plt, sizes, widget, x, y):
    fig, ax = plt.subplots()
    fig.set_size_inches(3, 3)
    ax.set(xlim=(0, 8), xticks=np.arange(1, 8), ylim=(0, 8), yticks=np.arange(1, 8))
    ax.scatter(x, y, s=sizes*5, color=widget.color or None, alpha=opacity)
    mo.hstack([widget, plt.gca()], justify="start", widths=[1, 1])
    return ax, fig


if __name__ == "__main__":
    app.run()

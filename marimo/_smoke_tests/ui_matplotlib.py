import marimo

__generated_with = "0.19.11"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    import matplotlib.pyplot as plt
    import numpy as np

    return mo, np, plt


@app.cell
def _(np):
    data = np.random.randn(10000, 2)
    x = data[:, 0]
    y = data[:, 1]
    return x, y


@app.cell
def _(mo, plt, x, y):
    plt.scatter(x=x, y=y, s=1)
    fig = mo.ui.matplotlib(plt.gcf())
    fig
    return (fig,)


@app.cell
def _(fig, x, y):
    fig.get_mask(x, y).sum()
    return


if __name__ == "__main__":
    app.run()

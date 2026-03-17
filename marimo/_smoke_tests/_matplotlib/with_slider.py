import marimo

__generated_with = "0.20.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    v = mo.ui.slider(start=6.28, stop=62.8, step=0.1, show_value=True)
    v
    return (v,)


@app.cell
def _(v):
    import numpy as np
    import matplotlib.pyplot as plt

    x = np.arange(0, 1, 0.001)
    y = np.sin(x * v.value)
    plt.plot(x, y)
    plt.show()
    return


if __name__ == "__main__":
    app.run()

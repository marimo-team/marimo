import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import matplotlib.pyplot as plt
    return (plt,)


@app.cell
def _(plt):
    import numpy as np

    plt.hist(np.random.rand(1000), bins=10)
    return


if __name__ == "__main__":
    app.run()

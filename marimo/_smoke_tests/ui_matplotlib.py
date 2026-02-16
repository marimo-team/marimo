import marimo

__generated_with = "0.19.11"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    import matplotlib.pyplot as plt
    import pymde
    import numpy as np

    return mo, plt, pymde


@app.cell
def _(pymde):
    mnist = pymde.datasets.MNIST() 
    return (mnist,)


@app.cell
def _(mnist, mo, pymde):
    @mo.persistent_cache
    def compute_embedding():
        return pymde.preserve_neighbors(
            mnist.data, constraint=pymde.Standardized(), verbose=True
        ).embed(verbose=True)

    return (compute_embedding,)


@app.cell
def _(compute_embedding):
    embedding = compute_embedding()
    return (embedding,)


@app.cell
def _(mo):
    mo.ui.dataframe
    return


@app.cell
def _(embedding, mnist, mo, plt):
    x = embedding[:, 0]
    y = embedding[:, 1]

    plt.scatter(x=x, y=y, s=0.05, cmap="Spectral", c=mnist.attributes["digits"])
    plt.yticks([-2.5, 0, 2.5])
    plt.xticks([-2.5, 0, 2.5])
    fig = mo.ui.matplotlib(plt.gca(), debounce=True, label="Hello, 🌏")
    fig
    return fig, x, y


@app.cell
def _(embedding, fig, x, y):
    embedding[fig.value.get_mask(x, y)]
    return


@app.cell
def _(fig):
    fig.value if fig.value else "No selection!"
    return


if __name__ == "__main__":
    app.run()

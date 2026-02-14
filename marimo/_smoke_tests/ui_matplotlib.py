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
def _(embedding, mnist, mo, plt):
    x = embedding[:, 0]
    y = embedding[:, 1]

    plt.scatter(x=x, y=y, s=0.1, cmap="Spectral", c=mnist.attributes["digits"])
    plt.xlim(-8, 8)
    plt.ylim(-8, 8)
    plt.yticks([-4, 0, 4])
    plt.xticks([-4, 0, 4])
    fig = mo.ui.matplotlib(plt.gcf())
    fig
    return fig, x, y


@app.cell
def _(fig, x, y):
    fig.get_mask(x, y).sum()
    return


if __name__ == "__main__":
    app.run()

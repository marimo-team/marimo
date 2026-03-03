# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pymde==0.1.18",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full")


@app.cell
def _(mo):
    mo.md("""
    # Rotational Invariance of Embeddings
    """)
    return


@app.cell
def _():
    import pymde

    return (pymde,)


@app.cell
def _():
    import matplotlib.pyplot as plt

    return (plt,)


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    degrees = mo.ui.slider(0, 360, step=5, label=r"$\theta$")
    return (degrees,)


@app.cell
def _(embedding, mde):
    E_X = mde.average_distortion(embedding)
    return (E_X,)


@app.cell
def _(E_X, degrees, mde, mo, rotated_embedding):
    _E_X_hat = mde.average_distortion(rotated_embedding)

    rotation = mo.md(
        rf"""
        ## Laplacian Embedding

        On the right is a Laplacian embedding of the MNIST dataset. This is formed
        by stacking the bottom eigenvectors (excluding the all-ones vector) of
        a Laplacian matrix representing a similarity graph on the data.

        ## Distortion

        Embeddings try to be faithful to the original data by minimizing
        the distortion between pairwise relationships of items, on average.
        For this embedding $X$, the average distortion is $E(X) = {E_X:0.4f}$.

        ## Rotational Invariance
        Embeddings are _rotationally invariant_: the distortion doesn't change
        with rotation.

        **Try it!** Rotate the embedding {degrees} degrees to
        produce a new embedding $\hat X$:

        \[
        \hat X = X \begin{{bmatrix}}
            \cos({degrees.value} \degree) & -\sin({degrees.value} \degree) \\
            \sin({degrees.value} \degree) & \cos({degrees.value} \degree)
        \end{{bmatrix}}
        \]


        The average distortion of the rotated embedding is $E(\hat X) = {_E_X_hat:0.4f}$,
        which should match $E(X)$!
        """
    ).style({"max-width": "550px"})
    return (rotation,)


@app.cell
def _(embedding, mnist, plt, pymde):
    import functools

    @functools.cache
    def rotate_embedding(degrees):
        rotated_embedding = pymde.rotate(embedding, degrees=degrees)
        ax = pymde.plot(
            rotated_embedding,
            color_by=mnist.attributes["digits"],
            marker_size=0.3,
            figsize_inches=(5, 5),
            axis_limits=(-3, 3),
        )
        plt.tight_layout()
        return rotated_embedding, ax

    return (rotate_embedding,)


@app.cell
def _(degrees, rotate_embedding):
    rotated_embedding, ax = rotate_embedding(degrees.value)
    return ax, rotated_embedding


@app.cell
def _(ax, mo, rotation):
    mo.hstack([rotation, mo.center(ax)], justify="start", align="start")
    return


@app.cell
def _(pymde):
    mnist = pymde.datasets.MNIST()
    return (mnist,)


@app.cell
def _(mnist, pymde):
    mde = pymde.laplacian_embedding(mnist.data, verbose=True)
    return (mde,)


@app.cell
def _(mde):
    embedding = mde.embed(verbose=True)
    return (embedding,)


if __name__ == "__main__":
    app.run()

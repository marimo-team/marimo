import marimo

__generated_with = "0.1.56"
app = marimo.App(width="full")


@app.cell
def __(mo):
    mo.md("# Rotational Invariance of Embeddings")
    return


@app.cell
def __():
    import pymde
    return pymde,


@app.cell
def __():
    import matplotlib.pyplot as plt
    return plt,


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    degrees = mo.ui.slider(0, 360, step=5, label=r"$\theta$")
    return degrees,


@app.cell
def __(embedding, mde):
    E_X = mde.average_distortion(embedding)
    return E_X,


@app.cell
def __(E_X, degrees, mde, mo, rotated_embedding):
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
    return rotation,


@app.cell
def __(embedding, mnist, plt, pymde):
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
    return functools, rotate_embedding


@app.cell
def __(degrees, rotate_embedding):
    rotated_embedding, ax = rotate_embedding(degrees.value)
    return ax, rotated_embedding


@app.cell
def __(ax, mo, rotation):
    mo.hstack([rotation, mo.center(ax)], justify="start", align="start")
    return


@app.cell
def __(pymde):
    mnist = pymde.datasets.MNIST()
    return mnist,


@app.cell
def __(mnist, pymde):
    mde = pymde.laplacian_embedding(mnist.data, verbose=True)
    return mde,


@app.cell
def __(mde):
    embedding = mde.embed(verbose=True)
    return embedding,


if __name__ == "__main__":
    app.run()

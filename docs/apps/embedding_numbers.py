import marimo

__generated_with = "0.0.5"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        """# Embedding MNIST

        This app shows how to use the function `pymde.preserve_neighbors`
        to produce embeddings that highlight the local structure of your
        data, using MNIST as a case study. In these embeddings similar
        digits are near each other, and dissimilar digits are not near each other.

        ## Data
        The data we'll embed are 70,000 28x28 grayscale images of handwritten
        digits:
        """
    )
    return


@app.cell
def __(button, show_random_images):
    button

    show_random_images(5)
    return


@app.cell
def __(mo):
    button = mo.ui.button(label="Click this button")
    mo.md(f"{button} _to view another random sample of images._").center()
    return button,


@app.cell
def __(mo):
    params = (
        mo.md(
            """
            ### Try these controls <span style="font-size: 28px">🎮</span>
            Here are some parameters you can play around with to control the
            embedding.

            - embedding dimension (2 or 3): {embedding_dimension}
            - constraint: {constraint_type}
            """
        )
        .batch(
            embedding_dimension=mo.ui.slider(2, 3, value=2),
            constraint_type=mo.ui.dropdown(
                ("Centered", "Standardized"), value="Centered"
            ),
        )
        .form()
    )

    params
    return params,


@app.cell
def __(params):
    if params.value is not None:
        embedding_dimension, constraint_type = (
            params.value["embedding_dimension"],
            params.value["constraint_type"],
        )
    else:
        embedding_dimension, constraint_type = None, None
    return constraint_type, embedding_dimension


@app.cell
def __(constraint_type, pymde):
    if constraint_type is not None:
        _constraints = {
            "Centered": pymde.Centered(),
            "Standardized": pymde.Standardized(),
        }

        constraint = _constraints[constraint_type]
    return constraint,


@app.cell
def __(
    compute_embedding,
    constraint,
    embedding_dimension,
    mnist,
    plt,
    pymde,
):
    def show_embedding():
        _, embedding = compute_embedding(embedding_dimension, constraint)
        pymde.plot(embedding, color_by=mnist.attributes["digits"])
        plt.tight_layout()
        return plt.gca()


    show_embedding() if embedding_dimension is not None else None
    return show_embedding,


@app.cell
def __(mnist, pymde, torch):
    embedding_cache = {}


    def compute_embedding(embedding_dim, constraint):
        key = (embedding_dim, constraint)
        if key in embedding_cache:
            return embedding_cache[key]

        mde = pymde.preserve_neighbors(
            mnist.data,
            embedding_dim=embedding_dim,
            constraint=constraint,
            device="cuda" if torch.cuda.is_available() else "cpu",
            verbose=True,
        )
        X = mde.embed(verbose=True)
        value = (mde, X)
        embedding_cache[key] = value
        return value
    return compute_embedding, embedding_cache


@app.cell
def __(pymde):
    mnist = pymde.datasets.MNIST()
    return mnist,


@app.cell
def __(mnist, plt, torch):
    def show_random_images(n_images):
        indices = torch.randperm(mnist.data.shape[0])[:n_images]
        images = mnist.data[indices].reshape((-1, 28, 28))
        fig, axes = plt.subplots(1, n_images)
        fig.set_size_inches(6.5, 1.5)
        for im, ax in zip(images, axes.flat):
            ax.imshow(im, cmap="gray")
            ax.set_yticks([])
            ax.set_xticks([])
        plt.tight_layout()
        return fig
    return show_random_images,


@app.cell
def __():
    import matplotlib.pyplot as plt
    import pymde
    import torch

    import marimo as mo
    return mo, plt, pymde, torch


if __name__ == "__main__":
    app.run()

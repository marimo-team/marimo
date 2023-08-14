import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        """
        # Sanity-Checking Embeddings

        This app shows you the basics of sanity-checking an embedding made with
        the `PyMDE` library. We'll use MNIST as a case study.
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        """
        We'll start by making a simple neighborhood-preserving embedding. This 
        means that we'll try to identify pairs of images that are similar, using
        a heuristic, and we'll tell PyMDE to place these pairs near each other in 
        the embedding.
        """
    )
    return


@app.cell
def __(n_neighbors):
    n_neighbors
    return


@app.cell
def __(n_neighbors):
    ready = n_neighbors.value is not None
    return ready,


@app.cell
def __(mo, ready):
    mo.md(
        """
        Below, we've plotted an embedding along with a CDF of the distortions
        per pair. We see that most pairs were embedded with
        very low distortion, but some pairs have much higher distortion
        that the rest. These will be interesting to examine up close.
        """
    ) if ready else None
    return


@app.cell
def __(mnist, plt, quadratic_mde, ready):
    def compute_embedding():
        _ = quadratic_mde.embed(verbose=True)
        quadratic_mde.plot(color_by=mnist.attributes["digits"])
        ax1 = plt.gca()
        quadratic_mde.distortions_cdf()
        ax2 = plt.gca()

        pairs, distortions = quadratic_mde.high_distortion_pairs()
        return pairs, distortions, (ax1, ax2)


    pairs, distortions, plots = (
        compute_embedding() if ready else (None, None, None)
    )
    plots
    return compute_embedding, distortions, pairs, plots


@app.cell
def __(mo):
    n_neighbors = mo.ui.slider(
        3, 30, step=1, value=15, label="Number of neighbors in $k$-NN graph"
    ).form()
    return n_neighbors,


@app.cell
def __(knn, n_neighbors, ready):
    knn_graph = knn(n_neighbors.value) if ready else None
    return knn_graph,


@app.cell
def __(functools, mnist, pymde):
    @functools.cache
    def knn(n_neighbors):
        return pymde.preprocess.k_nearest_neighbors(
            mnist.data, k=n_neighbors, verbose=True
        )

    return knn,


@app.cell
def __(knn_graph, mnist, pymde, ready, torch):
    def construct_mde_problem():
        if torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"

        return pymde.MDE(
            n_items=mnist.data.shape[0],
            embedding_dim=2,
            edges=knn_graph.edges,
            distortion_function=pymde.penalties.Quadratic(knn_graph.weights),
            constraint=pymde.Standardized(),
            device=device,
        )

    quadratic_mde = construct_mde_problem() if ready else None
    return construct_mde_problem, quadratic_mde


@app.cell
def __(mo, ready):
    mo.md(
        """
        ## Pairs with highest and lowest distortion

        Let's visualize a few pairs of images with low distortion (meaning they
        were similar and placed near each other by the embedding) and with high 
        distortion (meaning they were similar but the embedding failed to place 
        them near each other).
        """
    ) if ready else None
    return


@app.cell
def __(mo, ready):
    n_pairs = mo.ui.slider(5, 10, label="number of pairs")
    n_pairs if ready else None
    return n_pairs,


@app.cell
def __(mo, ready):
    mo.md(
        """### Low distortion pairs

        These are examples of pairs of images that were known to be similar,
        and that the embedding placed very near each other.
        """
    ) if ready else None
    return


@app.cell
def __(n_pairs, pairs, plot_pairs, ready):
    plot_pairs(pairs[-n_pairs.value :]) if ready else None
    return


@app.cell
def __(mo, ready):
    mo.md(
        """
        ### High distortion pairs

        Notice that some of these pairs of images are actually not the same digit;
        we told our embedding to put them close together, but the embedding refused
        to do so (in some cases, rightly so!). In other cases, the images in a pair
        do depict the same digit, but are very strangely drawn. In a very real 
        sense, these pairs can be considered to be **outliers** in our original 
        data.
        """
    ) if ready else None
    return


@app.cell
def __(n_pairs, pairs, plot_pairs, ready):
    plot_pairs(pairs[: n_pairs.value]) if ready else None
    return


@app.cell
def __(mnist, plt):
    def plot_pairs(pairs):
        fig, axs = plt.subplots(2, pairs.shape[0], figsize=(15.0, 3.0))
        for pair_index in range(pairs.shape[0]):
            i = pairs[pair_index][0]
            j = pairs[pair_index][1]
            im_i = mnist.data[i].reshape(28, 28)
            im_j = mnist.data[j].reshape(28, 28)
            axs[0][pair_index].imshow(im_i)
            axs[0][pair_index].set_xticks([])
            axs[0][pair_index].set_yticks([])
            axs[1][pair_index].imshow(im_j)
            axs[1][pair_index].set_xticks([])
            axs[1][pair_index].set_yticks([])
        plt.tight_layout()
        return plt.gca()
    return plot_pairs,


@app.cell
def __(pymde):
    mnist = pymde.datasets.MNIST()
    return mnist,


@app.cell
def __():
    import functools

    import matplotlib.pyplot as plt
    import pymde
    import torch

    import marimo as mo
    return functools, mo, plt, pymde, torch


if __name__ == "__main__":
    app.run()

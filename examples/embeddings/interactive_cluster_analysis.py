import marimo

__generated_with = "0.1.38"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Cluster analysis")
    return


@app.cell
def __(mo):
    mo.md(
        """
        Here's an **embedding of MNIST**: each point represents a digit,
        with similar digits close to each other.
        """
    )
    return


@app.cell
def __(compute_embedding, constraint, embedding_dimension):
    embedding = compute_embedding(embedding_dimension, constraint) 
    return embedding,


@app.cell
def __(alt, df, mo):
    chart = mo.ui.altair_chart(
        alt.Chart(df)
        .mark_circle(size=4)
        .encode(
            x=alt.X("x:Q").scale(domain=(-2.5, 2.5)),
            y=alt.Y("y:Q").scale(domain=(-2.5, 2.5)),
            color=alt.Color("digit:N"),
        )
        .properties(width=500, height=500),
        chart_selection="interval",
    )
    chart
    return chart,


@app.cell
def __(chart, mo):
    table = mo.ui.table(chart.value)
    return table,


@app.cell
def __(chart, mo, show_images, table):
    # mo.stop() prevents this cell from running if the chart has
    # no selection
    mo.stop(not len(chart.value))

    # show 10 images: either the first 10 from the selection, or the first ten
    # selected in the table
    selected_images = (
        show_images(list(chart.value["index"]))
        if not len(table.value)
        else show_images(list(table.value["index"]))
    )

    mo.md(
        f"""
        **Here's a preview of the images you've selected**:

        {mo.as_html(selected_images)}

        Here's all the data you've selected.

        {table}
        """
    )
    return selected_images,


@app.cell
def __(pymde):
    embedding_dimension = 2
    constraint = pymde.Standardized()
    return constraint, embedding_dimension


@app.cell
def __(embedding, mnist, pd, torch):
    indices = torch.randperm(mnist.data.shape[0])[:20000].numpy()
    embedding_sampled = embedding.numpy()[indices]

    df = pd.DataFrame(
        {
            "index": indices,
            "x": embedding_sampled[:, 0],
            "y": embedding_sampled[:, 1],
            "digit": mnist.attributes["digits"][indices],
        }
    )
    return df, embedding_sampled, indices


@app.cell
def __(functools, mnist, mo, pymde, torch):
    @functools.cache
    def compute_embedding(embedding_dim, constraint):
        mo.output.append(
            mo.md("Your embedding is being computed ... hang tight!").callout(kind="warn")
        )

        mde = pymde.preserve_neighbors(
            mnist.data,
            embedding_dim=embedding_dim,
            constraint=constraint,
            device="cuda" if torch.cuda.is_available() else "cpu",
            verbose=True,
        )
        X = mde.embed(verbose=True)
        mo.output.clear()
        return X
    return compute_embedding,


@app.cell
def __(pymde):
    mnist = pymde.datasets.MNIST()
    return mnist,


@app.cell
def __(mnist, plt):
    def show_images(indices, max_images=10):
        indices = indices[:max_images]
        images = mnist.data.reshape((-1, 28, 28))[indices]
        fig, axes = plt.subplots(1, len(indices))
        fig.set_size_inches(12.5, 1.5)
        if len(indices) > 1:
            for im, ax in zip(images, axes.flat):
                ax.imshow(im, cmap="gray")
                ax.set_yticks([])
                ax.set_xticks([])
        else:
            axes.imshow(images[0], cmap="gray")
            axes.set_yticks([])
            axes.set_xticks([])
        plt.tight_layout()
        return fig
    return show_images,


@app.cell
def __():
    import functools

    import matplotlib.pyplot as plt
    import pymde
    import torch

    import marimo as mo
    return functools, mo, plt, pymde, torch


@app.cell
def __():
    import altair as alt
    return alt,


@app.cell
def __():
    import pandas as pd
    return pd,


if __name__ == "__main__":
    app.run()

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair==5.4.1",
#     "duckdb==1.1.3",
#     "hdbscan==0.8.39",
#     "marimo",
#     "numba==0.60.0",
#     "numpy==2.0.2",
#     "polars==1.13.1",
#     "pyarrow==18.0.0",
#     "scikit-learn==1.5.2",
#     "umap-learn==0.5.7",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    # Data manipulation and database connections
    import polars as pl
    import duckdb
    import numba  # <- FYI, this module takes a while to load, be patient
    import pyarrow

    # Visualization
    import altair as alt
    import marimo as mo

    # ML tools for dimensionality reduction and clustering
    import umap  # For reducing high-dimensional embeddings to 2D
    import hdbscan  # For clustering similar embeddings
    import numpy as np
    from sklearn.decomposition import PCA

    return PCA, alt, hdbscan, mo, np, pl, umap


@app.cell
def _(mo):
    _df = mo.sql(
        """
        ATTACH IF NOT EXISTS 'md:my_db'
        """
    )
    return


@app.cell
def _(mo):
    _df = mo.sql(
        """
        CREATE OR REPLACE TABLE my_db.demo_embedding AS
        SELECT DISTINCT ON (url) *  -- Remove duplicate URLs
        FROM 'hf://datasets/julien040/hacker-news-posts/story.parquet'
        WHERE contains(title, 'database')  -- Filter for posts about databases
            AND score > 5  -- Only include popular posts
        LIMIT 50000;
        """
    )
    return


@app.cell
def _(mo):
    embeddings = mo.sql(
        """
        SELECT *, embedding(title) as text_embedding
        FROM my_db.demo_embedding
        LIMIT 1500;  -- Limiting for performance in this demo, but you can adjust this
        """
    )
    return (embeddings,)


@app.cell
def _(PCA, hdbscan, np, umap):
    def umap_reduce(np_array):
        """
        Reduce the dimensionality of the embeddings to 2D using
        UMAP algorithm. UMAP preserves both local and global structure
        of the high-dimensional data.
        """
        reducer = umap.UMAP(
            n_components=2,  # Reduce to 2D for visualization
            metric="cosine",  # Use cosine similarity for text embeddings
            n_neighbors=80,  # Higher values = more global structure
            min_dist=0.1,  # Controls how tightly points cluster
        )
        return reducer.fit_transform(np_array)

    def cluster_points(np_array, min_cluster_size=4, max_cluster_size=50):
        """
        Cluster the embeddings using HDBSCAN algorithm.
        We first reduce dimensionality to 50D with PCA to speed up clustering,
        while still preserving most of the important information.
        """
        pca = PCA(n_components=50)
        np_array = pca.fit_transform(np_array)

        hdb = hdbscan.HDBSCAN(
            min_samples=3,  # Minimum points to form dense region
            min_cluster_size=min_cluster_size,  # Minimum size of a cluster
            max_cluster_size=max_cluster_size,  # Maximum size of a cluster
        ).fit(np_array)

        return np.where(
            hdb.labels_ == -1, "outlier", "cluster_" + hdb.labels_.astype(str)
        )

    return cluster_points, umap_reduce


@app.cell
def _(cluster_points, embeddings, mo, umap_reduce):
    with mo.status.spinner("Clustering points...") as _s:
        embeddings_array = embeddings["text_embedding"].to_numpy()
        hdb_labels = cluster_points(embeddings_array)
        _s.update("Reducing dimensionality...")
        embeddings_2d = umap_reduce(embeddings_array)
    return embeddings_2d, hdb_labels


@app.cell
def _(embeddings, embeddings_2d, hdb_labels, pl):
    data = embeddings.lazy()  # Lazy evaluation for performance
    data = data.with_columns(
        text_embedding_2d_1=embeddings_2d[:, 0],
        text_embedding_2d_2=embeddings_2d[:, 1],
        cluster=hdb_labels,
    )
    data = data.unique(
        subset=["url"], maintain_order=True
    )  # Remove duplicate URLs
    data = data.drop(["text_embedding", "id"])  # Drop unused columns
    data = data.filter(pl.col("cluster") != "outlier")  # Filter out outliers
    data = data.collect()  # Collect the data
    data
    return (data,)


@app.cell
def _(alt, data, mo):
    chart = (
        alt.Chart(data)
        .mark_point()
        .encode(
            x=alt.X("text_embedding_2d_1").scale(zero=False),
            y=alt.Y("text_embedding_2d_2").scale(zero=False),
            color="cluster",
            tooltip=["title", "score", "cluster"],
        )
    )
    chart = mo.ui.altair_chart(chart)
    chart
    return (chart,)


@app.cell
def _(chart):
    chart.value
    return


if __name__ == "__main__":
    app.run()

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair==5.5.0",
#     "marimo",
#     "model2vec==0.6.0",
#     "polars==1.31.0",
#     "scikit-learn==1.7.1",
#     "umap-learn==0.5.9.post2",
# ]
# ///

import marimo

__generated_with = "0.14.13"
app = marimo.App(width="columns")


@app.cell
def _(mo):
    mo.md(
        r"""
        # Visualization: Embedding Summary and Bulk Selection 

        Create interactive dashboards using `mo.altair_chart` and `UMAP`.
        This technique is generally useful for any kind of embedding, but we're demonstrating it with text embeddings below.
        """
    )
    return



@app.cell
def _():
    import marimo as mo
    import polars as pl 
    import altair as alt
    from model2vec import StaticModel
    from umap import UMAP
    return StaticModel, UMAP, alt, mo, pl


@app.cell
def _(StaticModel, UMAP, pl):
    DATASET = "https://calmcode.io/static/data/clinc.csv"
    TEXT_COL = "text"

    df = pl.read_csv(DATASET).sample(10_000)
    
    # We're using Model2Vec because it so lightweight, sentence-transformers will also work!
    tfm = StaticModel.from_pretrained("minishlab/potion-base-8M")
    df = df.with_columns(emb=tfm.encode(df[TEXT_COL].to_list()))

    # UMAP turns the high-dimensional embeddings into 2D points which are easier to visualize.
    x_pca = UMAP(n_components=2).fit_transform(df["emb"].to_numpy())
    df = df.with_columns(x=x_pca[:, 0], y=x_pca[:, 1]).select(TEXT_COL, "x", "y")
    return TEXT_COL, df


@app.cell
def _(alt, df, mo):
    chart = mo.ui.altair_chart(alt.Chart(df).mark_point().encode(x="x", y="y").properties(width=500))
    return (chart,)


@app.cell
def _(TEXT_COL, chart, mo):
    mo.hstack([chart, chart.value.select(TEXT_COL)])
    return


if __name__ == "__main__":
    app.run()


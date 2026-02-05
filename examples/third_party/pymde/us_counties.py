# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pandas",
#     "pymde==0.1.18",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _(mo):
    mo.md("""
    # Embedding 🇺🇸 Counties

    This notebook accompanies chapter 10 of the monograph
    [Minimum-Distortion Embedding](https://web.stanford.edu/~boyd/papers/min_dist_emb.html).

    🇺🇸 In this example notebook, we use PyMDE to embed and visualize 3,220
    US counties, described by their demographic data (collected between 2013-
    2017 by an ACS longitudinal survey).

    🌎 We then color each county by the fraction of voters who voted for a
    democratic candidate in the 2016 presidential election. Interestingly, the
    embedding vaguely resembles a map of the US, clustered by political party
    preference, though no geographic or party preference data were
    used to compute the embedding!

    ⚡ We use `mo.ui.altair_chart` to create a reactive and interactive
    scatter plot of the embedding: this makes it possible to see where counties
    land in the embedding!
    """)
    return


@app.cell
def _():
    import pymde

    return (pymde,)


@app.cell
def _(pymde):
    dataset = pymde.datasets.counties()
    return (dataset,)


@app.cell
def _(mo):
    mo.md("""
    ## The data

    The data we embed includes demographic information about each county.
    """)
    return


@app.cell
def _(dataset, mo):
    mo.ui.table(dataset.county_dataframe, page_size=5)
    return


@app.cell
def _(mo):
    mo.md("""
    ## The embedding

    We now make a neighbor-preserving embedding, to explore the local
    relationships in the data.
    """)
    return


@app.cell
def _(dataset, pymde):
    mde = pymde.preserve_neighbors(data=dataset.data, verbose=True)
    return (mde,)


@app.cell
def _(mde):
    embedding = mde.embed()
    return (embedding,)


@app.cell
def _(mo):
    mo.md("""
    Finally we visualize the embedding, rotating it so that it vaguely
    resembles a map of the US. Note that counties that voted Republican tend
    to cluster together, as do counties that voted Democratic, even though
    our original data had no information about political party preference!

    In some real sense, the embedding "discovered" political preference
    from demographic data.
    """)
    return


@app.cell
def _(embedding, pymde):
    # Rotate the embedding by some amount of degrees
    rotated_embedding = pymde.rotate(embedding, -30.0)
    return (rotated_embedding,)


@app.cell
def _(dataset, pd, rotated_embedding):
    embedding_df = pd.concat(
        [
            pd.DataFrame(
                {
                    "x": rotated_embedding[:, 0],
                    "y": rotated_embedding[:, 1],
                    "democratic_fraction": dataset.attributes[
                        "democratic_fraction"
                    ],
                }
            ),
            dataset.county_dataframe,
        ],
        axis=1,
    )
    return (embedding_df,)


@app.cell
def _(mo):
    mo.md("""
    ### Try it! 👆

    Select points in the scatter plot below with your cursor: they're
    automatically sent back to Python, letting you investigate further!
    """)
    return


@app.cell
def _(alt, embedding_df, mo):
    plot = mo.ui.altair_chart(
        alt.Chart(data=embedding_df, width=400, height=400)
        .mark_circle(size=10, opacity=1)
        .encode(
            x="x",
            y="y",
            color=alt.Color("democratic_fraction").scale(scheme="redblue"),
        )
    )
    plot
    return (plot,)


@app.cell
def _(mo, plot):
    mo.ui.table(plot.value)
    return


@app.cell
def _():
    import matplotlib.pyplot as plt

    return


@app.cell
def _():
    import pandas as pd

    return (pd,)


@app.cell
def _():
    import altair as alt

    return (alt,)


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()

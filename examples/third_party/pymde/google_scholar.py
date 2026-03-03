# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pymde==0.1.18",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(r"""
    # Embedding Google Scholar

    This notebook shows how to use the function `pymde.preserve_distances` to
    produce embeddings of networks, in which the goal is to preserve the
    shortest-path distances in the network.

    It uses an academic co-authorship network collected from Google Scholar as
    a case study.
    """)
    return


@app.cell
def _():
    import pymde

    import matplotlib.pyplot as plt
    import numpy as np
    import torch

    return np, plt, pymde, torch


@app.cell
def _(pymde):
    gscholar = pymde.datasets.google_scholar()
    return (gscholar,)


@app.cell
def _(gscholar):
    scholars_df = gscholar.other_data['dataframe']
    scholars_df
    return


@app.cell
def _(gscholar):
    coauthorship_graph = gscholar.data
    return (coauthorship_graph,)


@app.cell
def _(coauthorship_graph):
    f'{coauthorship_graph.n_items:,} authors'
    return


@app.cell
def _(coauthorship_graph):
    f'{coauthorship_graph.n_edges:,} edges'
    return


@app.cell
def _(coauthorship_graph):
    print(f'edge density: {100*(coauthorship_graph.n_edges / (coauthorship_graph.n_all_edges)):.2f} percent')
    return


@app.cell
def _(DEVICE, coauthorship_graph, pymde):
    mde = pymde.preserve_distances(
        data=coauthorship_graph,
        loss=pymde.losses.Absolute,
        max_distances=1e8,
        device=DEVICE,
        verbose=True)

    mde.embed(verbose=True)
    return (mde,)


@app.cell
def _(mde, np, plt):
    plt.figure(figsize=(12, 3))
    original_distances = np.sort(mde.distortion_function.deviations.cpu().numpy())
    ax = plt.gca()
    plt.hist(original_distances, histtype='step', bins=np.arange(1, 11), density=True, cumulative=True)
    plt.xlim(1, 10)
    plt.xticks(np.arange(1, 11))
    plt.xlabel('graph distances')
    plt.show()
    return


@app.cell
def _(mde):
    mde.distortions_cdf()
    return


@app.cell
def _(gscholar, mde):
    mde.plot(color_by=gscholar.attributes['coauthors'], color_map='viridis',
             figsize_inches=(12., 12.), background_color='k')
    return


@app.cell
def _(coauthorship_graph, gscholar, mde, plt, torch):
    edges = coauthorship_graph.edges
    indices = torch.randperm(edges.shape[0])[:1000]
    edges = edges[indices].cpu().numpy()

    _ax = mde.plot(edges=edges, color_by=gscholar.attributes['coauthors'], color_map='viridis', figsize_inches=(12, 12))
    plt.tight_layout()
    _ax
    return


@app.cell
def _(gscholar):
    from matplotlib import colors


    legend = {
        'bio': colors.to_rgba('tab:purple'),
        'ai': colors.to_rgba('tab:red'),
        'cs': colors.to_rgba('tab:cyan'),
        'ee': colors.to_rgba('tab:green'),
        'physics': colors.to_rgba('tab:orange')
    }
    scholar_disciplines_df = gscholar.other_data['disciplines']
    topic_colors = [legend[code] for code in scholar_disciplines_df['topic']]
    return scholar_disciplines_df, topic_colors


@app.cell
def _(mde, pymde, scholar_disciplines_df, topic_colors):
    pymde.plot(mde.X[scholar_disciplines_df['node_id'].values], colors=topic_colors,
               figsize_inches=(12, 12), background_color='black')
    return


@app.cell
def _(torch):
    DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
    return (DEVICE,)


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()

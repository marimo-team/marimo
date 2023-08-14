import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Drawing Graphs")
    return


@app.cell
def __(mo):
    n_items = mo.ui.slider(3, 15)
    return n_items,


@app.cell
def __(mo, n_items):
    mo.md(f"Embedding graphs on {n_items} **{n_items.value}** items")
    return


@app.cell
def __(draw_graphs, loss, n_items, penalty):
    draw_graphs(n_items, penalty, loss)
    return


@app.cell
def __(mo, pymde):
    penalties = {
        "Linear": pymde.penalties.Linear,
        "Quadratic": pymde.penalties.Quadratic,
        "Cubic": pymde.penalties.Cubic,
    }

    penalty = mo.ui.dropdown(penalties.keys(), "Cubic", label="penalty")
    return penalties, penalty


@app.cell
def __(mo, pymde):
    losses = {
        "Linear": pymde.losses.Absolute,
        "Quadratic": pymde.losses.Quadratic,
        "WeightedQuadratic": pymde.losses.WeightedQuadratic,
    }
    loss = mo.ui.dropdown(losses.keys(), "WeightedQuadratic", label="loss")
    return loss, losses


@app.cell
def __(complete_graph, mo, tree):
    def draw_graphs(n_items, penalty, loss):
        complete_graph_tab = [penalty, complete_graph(n_items.value, penalty.value)]
        tree_tab = [loss, tree(n_items.value, loss.value)]
        return mo.tabs(
            {
                "Complete graph": complete_graph_tab,
                "Binary tree": tree_tab,
            }
        )
    return draw_graphs,


@app.cell
def __():
    embedding_dim = 2
    return embedding_dim,


@app.cell
def __(format_axis, functools, penalties, pymde):
    @functools.cache
    def complete_graph(n_items, penalty):
        edges = pymde.all_edges(n_items)
        mde = pymde.MDE(
            n_items,
            embedding_dim=2,
            edges=edges,
            distortion_function=penalties[penalty](weights=1.0),
            constraint=pymde.Standardized(),
        )
        mde.embed(verbose=False)
        return format_axis(mde.plot(edges=edges))
    return complete_graph,


@app.cell
def __(embedding_dim, format_axis, functools, losses, pymde, torch):
    @functools.cache
    def tree(n_items, loss):
        edges = []
        stack = [0]
        while stack:
            root = stack.pop()
            c1 = root * 2 + 1
            c2 = root * 2 + 2
            if c1 < n_items:
                edges.append((root, c1))
                stack.append(c1)
            if c2 < n_items:
                edges.append((root, c2))
                stack.append(c2)
        tree = pymde.Graph.from_edges(torch.tensor(edges))
        shortest_paths_graph = pymde.preprocess.graph.shortest_paths(tree)

        mde = pymde.MDE(
            n_items,
            embedding_dim,
            shortest_paths_graph.edges,
            losses[loss](shortest_paths_graph.distances),
        )
        mde.embed(snapshot_every=1, max_iter=20, verbose=False)
        return format_axis(mde.plot(edges=tree.edges))
    return tree,


@app.cell
def __():
    def format_axis(ax):
        ax.figure.set_size_inches(3.5, 3.5)
        ax.set_title("embedding")
        ax.figure.tight_layout()
        ax.set_xticks([])
        ax.set_yticks([])
        return ax
    return format_axis,


@app.cell
def __():
    import marimo as mo
    import pymde

    import functools
    import numpy as np
    import scipy.sparse as sp
    import torch
    return functools, mo, np, pymde, sp, torch


if __name__ == "__main__":
    app.run()

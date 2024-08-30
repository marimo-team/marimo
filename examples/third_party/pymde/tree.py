import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo, n_items):
    mo.md(
        f"""
        # Embedding binary trees

        In this example, we'll use PyMDE to draw binary trees. Sweep the
        slider to draw bigger trees ...

        {n_items}
        """
    )
    return


@app.cell
def __(mo, n_items):
    mo.md(f"Let's embed a binary tree on **{n_items.value}** vertices.")
    return


@app.cell
def __(embedding, pymde, tree):
    pymde.plot(embedding, edges=tree.edges)
    return


@app.cell
def __(embed, make_graph, n_items):
    tree, graph = make_graph(n_items.value)
    embedding = embed(graph)
    return embedding, graph, tree


@app.cell
def __(mo):
    n_items = mo.ui.slider(64, 1024, step=64)
    return n_items,


@app.cell
def __(functools, pymde, torch):
    @functools.cache
    def make_graph(n_items):
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
        return tree, pymde.preprocess.graph.shortest_paths(tree)
    return make_graph,


@app.cell
def __(functools, pymde):
    @functools.cache
    def embed(shortest_paths_graph):
        mde = pymde.MDE(
            shortest_paths_graph.n_items,
            embedding_dim=2,
            edges=shortest_paths_graph.edges,
            distortion_function=pymde.losses.WeightedQuadratic(
                shortest_paths_graph.distances
            ),
        )
        return mde.embed(verbose=True)
    return embed,


@app.cell
def __():
    import functools

    import pymde
    import torch

    import marimo as mo
    return functools, mo, pymde, torch


if __name__ == "__main__":
    app.run()

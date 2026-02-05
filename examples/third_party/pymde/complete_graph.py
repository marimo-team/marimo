# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
#     "pymde==0.1.18",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Visualizing Complete Graphs
    """)
    return


@app.cell
def _(mo):
    n_items = mo.ui.slider(start=3, stop=64, step=1)
    mo.md(
        f"""
        Choose a number of items $n$: {n_items}
        """
    )
    return (n_items,)


@app.cell
def _(mo, pymde):
    penalty_function = mo.ui.dropdown(
        options={
            "Linear": pymde.penalties.Linear,
            "Quadratic": pymde.penalties.Quadratic,
            "Cubic": pymde.penalties.Cubic
        },
        value="Cubic"
    )
    mo.md(
        f"""
        Choose a penalty function: {penalty_function}
        """
    )
    return (penalty_function,)


@app.cell
def _(complete_graph, mo, n_items, penalty_function):
    plot = complete_graph(n_items.value, penalty_function.value)

    mo.md(
        f"""
        Here is a plot of $K_n$ with $n={n_items.value}$, i.e., a complete graph on
        ${n_items.value}$ nodes. This graph has

        \\[
        (n)(n-1)/2 = {n_items.value*(n_items.value-1)//2}
        \\]

        edges. The plot was obtained using a
        {penalty_function.value.__name__.lower()} penalty function.

        {mo.as_html(plot)}
        """
    )
    return


@app.cell
def _(pymde):
    import functools

    @functools.cache
    def complete_graph(n_items, penalty_function):
        edges = pymde.all_edges(n_items)
        mde = pymde.MDE(
            n_items,
            embedding_dim=2,
            edges=edges,
            distortion_function=penalty_function(weights=1.0),
            constraint=pymde.Standardized()
        )
        mde.embed(verbose=True)
        return mde.plot(edges=edges)

    return (complete_graph,)


@app.cell
def _():
    import pymde

    return (pymde,)


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()

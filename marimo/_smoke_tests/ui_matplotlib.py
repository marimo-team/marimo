import marimo

__generated_with = "0.20.1"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    import matplotlib.pyplot as plt
    import pymde
    import numpy as np

    return mo, np, plt, pymde


@app.cell
def _(pymde):
    mnist = pymde.datasets.MNIST() 
    return (mnist,)


@app.cell
def _(mnist, mo, pymde):
    @mo.persistent_cache
    def compute_embedding():
        return pymde.preserve_neighbors(
            mnist.data, constraint=pymde.Standardized(), verbose=True
        ).embed(verbose=True)

    return (compute_embedding,)


@app.cell
def _(compute_embedding):
    embedding = compute_embedding()
    return (embedding,)


@app.cell
def _(embedding, mnist, plt, pymde):
    x = embedding[:, 0]
    y = embedding[:, 1]

    ax = pymde.plot(X=embedding, color_by=mnist.attributes["digits"])
    plt.tight_layout()
    return ax, x, y


@app.cell
def _(ax, mo):
    fig = mo.ui.matplotlib(ax)
    fig
    return (fig,)


@app.cell
def _(embedding, fig, x, y):
    embedding[fig.value.get_mask(x, y)]
    return


@app.cell
def _(fig):
    fig.value if fig.value else "No selection!"
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Edge-data test

    Points are clustered right at the axes edges. Clicking on tick labels,
    axis labels, or the title should **not** start a selection. Previously
    the click was clamped to the nearest edge, which would select these
    edge points via `get_mask()`.
    """)
    return


@app.cell
def _(np, plt):
    rng = np.random.default_rng(99)
    # Points hugging the four edges of [0, 10] x [0, 10]
    edge_n = 30
    edge_x = np.concatenate([
        rng.uniform(0, 0.3, edge_n),        # left edge
        rng.uniform(9.7, 10, edge_n),       # right edge
        rng.uniform(0, 10, edge_n),          # bottom edge
        rng.uniform(0, 10, edge_n),          # top edge
        rng.uniform(3, 7, edge_n),           # centre (control)
    ])
    edge_y = np.concatenate([
        rng.uniform(0, 10, edge_n),          # left edge
        rng.uniform(0, 10, edge_n),          # right edge
        rng.uniform(0, 0.3, edge_n),         # bottom edge
        rng.uniform(9.7, 10, edge_n),        # top edge
        rng.uniform(3, 7, edge_n),           # centre (control)
    ])

    plt.figure()
    plt.scatter(edge_x, edge_y, s=20, c=edge_y, cmap="viridis")
    plt.colorbar(label="y value")
    plt.xlim(0, 10)
    plt.ylim(0, 10)
    plt.xlabel("X axis (click here should NOT select)")
    plt.ylabel("Y axis (click here should NOT select)")
    plt.title("Title area (click here should NOT select)")
    edge_ax = plt.gca()
    return edge_ax, edge_x, edge_y


@app.cell
def _(edge_ax, mo):
    edge_fig = mo.ui.matplotlib(edge_ax)
    edge_fig
    return (edge_fig,)


@app.cell
def _(edge_fig, edge_x, edge_y):
    _m = edge_fig.value.get_mask(edge_x, edge_y)
    f"Selected {_m.sum()} / {len(edge_x)} points"
    return


@app.cell
def _(edge_fig):
    edge_fig.value if edge_fig.value else "No selection!"
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Log-scale axes test
    """)
    return


@app.cell
def _(np, plt):
    # Exponentially distributed data for log-scale testing
    np.random.seed(42)
    log_x = np.random.lognormal(mean=2, sigma=1, size=500)
    log_y = np.random.lognormal(mean=3, sigma=0.8, size=500)

    plt.figure()
    plt.scatter(log_x, log_y, s=10, alpha=0.6)
    plt.yscale("log")
    plt.xlabel("X (linear scale)")
    plt.ylabel("Y (log scale)")
    plt.title("Log-scale scatter")
    log_ax = plt.gca()
    return log_ax, log_x, log_y


@app.cell
def _(log_ax, mo):
    log_fig = mo.ui.matplotlib(log_ax)
    log_fig
    return (log_fig,)


@app.cell
def _(log_fig, log_x, log_y, np):
    _m = log_fig.value.get_mask(log_x, log_y)
    log_x_sel, log_y_sel  = log_x[_m], log_y[_m]
    np.column_stack([log_x_sel, log_y_sel])
    return


@app.cell
def _(log_fig):
    log_fig.value if log_fig.value else "No selection!"
    return


if __name__ == "__main__":
    app.run()

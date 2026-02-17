import marimo

__generated_with = "0.19.11"
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
def _(embedding, mnist, plt):
    x = embedding[:, 0]
    y = embedding[:, 1]

    plt.scatter(x=x, y=y, s=0.05, cmap="Spectral", c=mnist.attributes["digits"])
    plt.yticks([-2.5, 0, 2.5])
    plt.xticks([-2.5, 0, 2.5])
    ax = plt.gca()
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

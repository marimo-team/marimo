import marimo

__generated_with = "0.19.11"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    vector = mo.ui.vector(
        [1, 0, 0, 0, 0],
        min_value=-5,
        max_value=5,
        step=0.1,
        precision=1,
        label="$\\vec{v}$",
    )
    vector
    return (vector,)


@app.cell
def _(vector):
    vector.value
    return


if __name__ == "__main__":
    app.run()

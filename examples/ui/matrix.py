import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    matrix = mo.ui.matrix(
        [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        min_value=-5,
        max_value=5,
        step=0.1,
        precision=1,
        label="$I$",
    )
    matrix
    return (matrix,)


@app.cell
def _(matrix):
    matrix.value
    return


if __name__ == "__main__":
    app.run()

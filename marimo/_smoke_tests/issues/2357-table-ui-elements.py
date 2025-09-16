import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    data = [{"x": 1, "y": "a", "c": mo.ui.button(label="hello")}, {"x": 2, "y": "b", "c": mo.ui.button(label="world")}]
    return (data,)


@app.cell
def _(data, mo):
    mo.ui.table(data)
    return


if __name__ == "__main__":
    app.run()

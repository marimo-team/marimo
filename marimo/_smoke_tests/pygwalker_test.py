import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import pygwalker

    from vega_datasets import data
    return data, pygwalker


@app.cell
def _(data, pygwalker):
    df = data.iris()
    pygwalker.walk(df)
    return


if __name__ == "__main__":
    app.run()

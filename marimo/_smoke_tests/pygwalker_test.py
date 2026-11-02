import marimo

__generated_with = "0.25.2"
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


if __name__ == "__main__":
    app.run()

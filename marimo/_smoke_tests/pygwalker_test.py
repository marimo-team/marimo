import marimo

__generated_with = "0.9.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import pygwalker

    from vega_datasets import data
    return data, pygwalker


@app.cell
def __(data, pygwalker):
    df = data.iris()
    pygwalker.walk(df)
    return (df,)


if __name__ == "__main__":
    app.run()

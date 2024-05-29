import marimo

__generated_with = "0.6.11"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    from vega_datasets import data
    return data, mo


@app.cell
def __():
    import altair as alt
    return alt,


@app.cell
def __(data, mo):
    options = data.list_datasets()
    dropdown = mo.ui.dropdown(options)
    dropdown
    return dropdown, options


@app.cell
def __(data, dropdown, mo):
    mo.stop(not dropdown.value)
    df = data.__call__(dropdown.value)
    df
    return df,


@app.cell
def __(df):
    import polars as pl
    polars_df = pl.DataFrame(df)
    return pl, polars_df


if __name__ == "__main__":
    app.run()

import marimo

__generated_with = "0.11.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import polars as pl
    return (pl,)


@app.cell
def _(pl):
    test_df = pl.DataFrame({"num": [0, 1]})
    return (test_df,)


@app.cell
def _(mo, test_df):
    table = mo.ui.table(test_df.to_dict(as_series=False))
    table
    return (table,)


@app.cell
def _(table):
    table.value
    return


@app.cell
def test_is_dict_of_lists(table):
    assert "num" in table.value
    assert isinstance(table.value["num"], list)
    return


if __name__ == "__main__":
    app.run()

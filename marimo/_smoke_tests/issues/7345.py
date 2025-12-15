import marimo

__generated_with = "0.18.4"
app = marimo.App(width="columns")


@app.cell(column=0)
def _():
    import marimo as mo
    import narwhals as nw
    import polars as pl
    import pandas as pd
    return mo, pd, pl


@app.cell
def _(pd, pl):
    data = data = {
        "A": ["foo", "foo", "foo", "foo", "foo", "bar", "bar", "bar", "bar"],
        "B": ["one", "one", "one", "two", "two", "one", "one", "two", "two"],
        "C": [
            "small",
            "large",
            "large",
            "small",
            "small",
            "large",
            "small",
            "small",
            "large",
        ],
        "D": [1, 2, 2, 3, 3, 4, 5, 6, 7],
        "E": [2, 4, 5, 5, 6, 6, 8, 9, 9],
        "F": [True, False, False, False, True, True, False, False, True],
    }

    pl_df = pl.DataFrame(data)
    pd_df = pd.DataFrame(data)
    return pd_df, pl_df


@app.cell
def _():
    return


@app.cell(column=1)
def _(mo, pd_df):
    mo.ui.dataframe(pd_df)
    return


@app.cell
def _(mo, pl_df):
    mo.ui.dataframe(pl_df)
    return


@app.cell
def _():
    return


@app.cell(column=2)
def _(pd_df):
    pd_df_next = pd_df
    pd_df_next = pd_df_next.pivot_table(index=["B"], columns=["A"], values=["F"], aggfunc="sum", sort=False, fill_value=0).sort_index(axis=0)
    pd_df_next.columns = [f"{'_'.join(map(str, col)).strip()}_sum" if isinstance(col, tuple) else f"{col}_sum" for col in pd_df_next.columns]
    pd_df_next = pd_df_next.reset_index()
    pd_df_next
    return


@app.cell
def _(pl_df):
    pl_df_next = pl_df
    pl_df_next = pl_df_next.pivot(
        on=["A", "F"],
        index=["B", "C"],
        values=["D"],
        aggregate_function="mean",
    )

    replacements = str.maketrans({'{': '', '}': '', '"': '', ',': '_'})
    pl_df_next.rename(lambda col: f'D_{col.translate(replacements)}_mean' if col not in ['B', 'C'] else col)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()

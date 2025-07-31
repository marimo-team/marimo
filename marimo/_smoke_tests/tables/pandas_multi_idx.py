import marimo

__generated_with = "0.13.12"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    return mo, pd


@app.cell
def _(mo, pd):
    arrays = [
        ["bar", "bar"],
        ["one", "two"],
    ]
    tuples = list(zip(*arrays))
    index = pd.MultiIndex.from_tuples(tuples, names=["first", "second"])
    named_indexes = pd.Series([1, 2], index=index)

    mo.vstack([mo.md("## Named indexes (works)"), named_indexes])
    return


@app.cell
def _(mo, pd):
    unnamed_indexes = pd.concat(
        {
            "a": pd.DataFrame({"foo": [1]}, index=["hello"]),
            "b": pd.DataFrame({"baz": [2.0]}, index=["world"]),
        }
    )

    mo.md(f"""
    ## Unnamed indexes does not work correctly

    {mo.vstack([mo.plain(unnamed_indexes), unnamed_indexes])}

    ### Using reset_index works but changes structure
    {mo.ui.table(unnamed_indexes.reset_index())}
    """)
    return


@app.cell
def _(mo, pd):
    _multi_idx = pd.MultiIndex.from_tuples([("weight", "kg"), ("height", "m")])
    _df = pd.DataFrame(
        [[1.0, 2.0], [3.0, 4.0]], index=["cat", "dog"], columns=_multi_idx
    )
    _multi_col_stack = _df.stack(future_stack=True)
    mo.vstack([mo.plain(_multi_col_stack), _multi_col_stack])

    mo.vstack(
        [
            mo.md("## Row multi-idx with stack (not working correctly)"),
            mo.plain(_multi_col_stack),
            _multi_col_stack,
        ]
    )
    return


@app.cell
def _(pd):
    cols = pd.MultiIndex.from_arrays(
        [["basic_amt"] * 2, ["NSW", "QLD"]], names=[None, "Faculty"]
    )
    idx = pd.Index(["All", "Full"])
    column_multi_idx = pd.DataFrame([(1, 1), (0, 1)], index=idx, columns=cols)
    return (column_multi_idx,)


@app.cell
def _(column_multi_idx, mo):
    mo.vstack(
        [
            mo.md("## Column multi index (we flatten)"),
            mo.plain(column_multi_idx),
            column_multi_idx,
        ]
    )
    return


if __name__ == "__main__":
    app.run()

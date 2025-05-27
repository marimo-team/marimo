import marimo

__generated_with = "0.12.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    return mo, pd


@app.cell
def _(pd):
    arrays = [
        ["bar", "bar"],
        ["one", "two"],
    ]
    tuples = list(zip(*arrays))
    index = pd.MultiIndex.from_tuples(tuples, names=["first", "second"])
    named_indexes = pd.Series([1, 2], index=index)
    named_indexes
    return arrays, index, named_indexes, tuples


@app.cell
def _(pd):
    unnamed_indexes = pd.concat(
        {
            "a": pd.DataFrame({"foo": [1]}, index=["hello"]),
            "b": pd.DataFrame({"baz": [2.0]}, index=["world"]),
        }
    )
    unnamed_indexes
    # unnamed_indexes.reset_index() # this works
    return (unnamed_indexes,)


@app.cell
def _(mo, pd):
    cols = pd.MultiIndex.from_arrays(
        [["basic_amt"] * 2, ["NSW", "QLD"]], names=[None, "Faculty"]
    )
    idx = pd.Index(["All", "Full"])
    column_multi_idx = pd.DataFrame([(1, 1), (0, 1)], index=idx, columns=cols)

    mo.ui.table(column_multi_idx)
    return cols, column_multi_idx, idx


@app.cell
def _(column_multi_idx):
    print("Raw data:\n", column_multi_idx)
    return


if __name__ == "__main__":
    app.run()

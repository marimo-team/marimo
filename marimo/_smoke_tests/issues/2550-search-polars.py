import marimo

__generated_with = "0.9.4"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import polars as pl
    import pandas

    data = pl.DataFrame(
        {
            "A": [1, 2, 3],
            "B": ["foo", "bar", "baz"],
            "C": [True, False, True],
            "D": [["zz", "yyy"], [], []],
            "E": [1.1, 2.2, 3.3],
            "F": [[12, 34], [], []],
        }
    )
    return data, mo, pandas, pl


@app.cell
def __(data):
    data.to_pandas()
    return


@app.cell
def __(data):
    data
    return


if __name__ == "__main__":
    app.run()

# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "polars",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="full")


@app.cell
def _():
    import polars as pl
    import altair as alt

    # https://github.com/vega/altair/blob/32990a597af7c09586904f40b3f5e6787f752fa5/doc/user_guide/encodings/index.rst#escaping-special-characters-in-column-names

    df1 = pl.DataFrame(
        {
            "a": [0.0, 0.0, 0.2, 0.2],
            "b": [True, False, False, False],
            "c": [True, False, False, False],
            "d": [True, False, False, False],
        }
    )
    df1
    return (pl,)


@app.cell
def _(pl):
    df2 = pl.DataFrame(
        {
            "i.a": [0.0, 0.0, 0.2, 0.2],
            "i.b": [True, False, False, False],
            "i[c]": [True, False, False, False],
            "i:d": [True, False, False, False],
        }
    )
    df2
    return


if __name__ == "__main__":
    app.run()

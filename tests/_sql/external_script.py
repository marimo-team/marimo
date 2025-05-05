# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "duckdb==1.2.2",
#     "marimo",
#     "pandas==2.2.3",
#     "sqlglot==26.16.4",
# ]
# ///

import marimo

__generated_with = "0.13.1"
app = marimo.App(width="medium")

with app.setup:
    import pandas as pd

    import marimo as mo

    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    not_used = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})


@app.function
def f(x):
    return 1 / x


@app.cell
def _():
    _df = mo.sql(
        """
        SELECT * FROM df
        """
    )
    return


@app.cell
def _():
    f(1)
    f(0)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()

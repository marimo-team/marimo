import marimo

__generated_with = "0.17.0"
app = marimo.App(width="medium", sql_output="native")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import numpy as np
    import sqlglot
    import pyarrow
    return np, pd


@app.cell
def _(np, pd):
    example_df = pd.DataFrame(
        [
            [np.random.random(size=[2, 2]) for _col in range(2)]
            for _row in range(3)
        ],
        columns=["A", "B"],
    )
    return (example_df,)


@app.cell
def _(example_df):
    import duckdb

    res = duckdb.sql(
        f"""
        SELECT COUNT(*) FROM example_df
        """,
    )
    print(res)
    return


if __name__ == "__main__":
    app.run()

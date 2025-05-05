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

__generated_with = "0.13.4"
app = marimo.App(width="medium")

with app.setup:
    import pandas as pd

    import marimo as mo

    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    not_used = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})


@app.cell
def script_hook_args(df1):
    _df = mo.sql(
        f"""
        SELECT * FROM df1
        """,
        tables={
            "df1": df1
        }
    )
    return


@app.cell
def script_hook_no_args():
    _df = mo.sql(
        f"""
        SELECT * FROM df
        """,
        tables={
            "df": df
        }
    )
    return


@app.cell
def _():
    df1 = df
    return (df1,)


if __name__ == "__main__":
    app.run()

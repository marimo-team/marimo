import marimo

__generated_with = "0.18.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import pandas as pd

    base = pd.Timestamp("2024-11-21T12:34:56")
    data = {
        "timestamp": [
            base,
            base + pd.Timedelta(milliseconds=0),
            base + pd.Timedelta(milliseconds=4),
            base + pd.Timedelta(milliseconds=9),
            base + pd.Timedelta(milliseconds=99),
            base + pd.Timedelta(milliseconds=999),
        ],
    }
    df = pd.DataFrame(data)
    pandas_dates_df = df
    pandas_dates_df
    return (pandas_dates_df,)


@app.cell
def _(pandas_dates_df):
    import polars as pl

    pl.DataFrame(pandas_dates_df)
    return


@app.cell
def _(mo):
    df_sql_dates = mo.sql(
        f"""
        SELECT raw,
               TRY_CAST(raw AS TIMESTAMP) AS parsed,
               raw LIKE '%.%' AS has_millis
        FROM (VALUES
          ('2023-01-01 12:00:00'),
          ('2023-01-01 12:00:00.123'),
          ('2023-06-30T23:59:59'),
          ('2023-06-30T23:59:59.999'),
          ('2022-12-31 00:00:00.000'),
          ('2022-12-31 00:00:00'),
          ('2023-05-01T08:30:00.456Z'),
          ('2023-05-01T08:30:00Z')
        ) AS t(raw)
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(f"""
    Created a pandas DataFrame (pandas_dates_df) containing a variety of date strings — some with milliseconds and some without.
    Columns:
    - raw: original string
    - parsed: parsed timestamp (NaT if parsing failed)
    - has_millis: boolean indicating presence of fractional seconds

    Also created an equivalent SQL result (df_sql_dates) using an inline VALUES list and TRY_CAST to show parsed timestamps and a simple LIKE check to detect milliseconds.
    """)
    return


if __name__ == "__main__":
    app.run()

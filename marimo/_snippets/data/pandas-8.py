# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.8"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Pandas DataFrame: Filter by Timestamp using TimeDelta string
        """
    )
    return


@app.cell
def __():
    import pandas as pd

    df = pd.DataFrame(
        {
            "time": [
                "2022-09-14 00:52:00-07:00",
                "2022-09-14 00:52:30-07:00",
                "2022-09-14 01:52:30-07:00",
            ],
            "letter": ["A", "B", "C"],
        }
    )
    df["time"] = pd.to_datetime(df.time)

    def rows_in_time_range(df, time_column, start_ts_str, timedelta_str):
        # Return rows from df, where start_ts < time_column <= start_ts + delta.
        # start_ts_str can be a date '2022-09-01' or a time '2022-09-14 00:52:00-07:00'
        # timedelta_str examples: '2 minutes'  '2 days 2 hours 15 minutes 30 seconds'
        start_ts = pd.Timestamp(start_ts_str).tz_localize("US/Pacific")
        end_ts = start_ts + pd.to_timedelta(timedelta_str)
        return df.query("@start_ts <= {0} < @end_ts".format(time_column))

    rows_in_time_range(df, "time", "2022-09-14 00:00", "52 minutes 31 seconds")
    return df, pd, rows_in_time_range


@app.cell
def __():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()

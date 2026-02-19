import marimo

__generated_with = "0.17.8"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    from datetime import datetime
    return datetime, mo, pd


@app.cell
def _(mo, pd):
    date_df = pd.DataFrame(
        {
            "dates": ["10/6/2025 14:17", "10/6/2025 14:18"],
            "date_series": pd.Series(pd.date_range("2000", freq="D", periods=2)),
        }
    )
    date_df["date_only"] = pd.to_datetime(date_df.dates).dt.date
    mo.vstack([mo.plain(date_df), date_df])
    return


@app.cell
def _(datetime, mo, pd):
    time = pd.DataFrame(
        {
            "s": [pd.to_datetime(1490195805, unit="s")],
            "ns": [pd.to_datetime(1490195805433502912, unit="ns")],
            "times": [
                pd.to_datetime(
                    [1, 2, 3], unit="D", origin=pd.Timestamp("1960-01-01")
                )
            ],
            "delta": [pd.to_timedelta(["1 days 06:05:01.00003", "15.5us", "nan"])],
            "format": [
                pd.to_datetime(
                    "2018-10-26 12:00:00.0000000011", format="%Y-%m-%d %H:%M:%S.%f"
                )
            ],
            "not_a_time": [
                pd.to_datetime("13000101", format="%Y%m%d", errors="coerce")
            ],
            "timezone": [
                pd.to_datetime(
                    ["2018-10-26 12:00 -0500", "2018-10-26 13:00 -0500"]
                )
            ],
            "mixed_timezone": [
                pd.to_datetime(
                    ["2020-01-01 01:00:00-01:00", datetime(2020, 1, 1, 3, 0)]
                )
            ],
            "with_utc_true": [
                pd.to_datetime(
                    ["2018-10-26 12:00", datetime(2020, 1, 1, 18)], utc=True
                )
            ],
        }
    ).transpose()
    mo.vstack([mo.plain(time), time])
    return


@app.cell
def _(mo, pd):
    date_ranges = pd.DataFrame(
        {
            "date_range": [
                pd.date_range(
                    start=pd.to_datetime("1/1/2018").tz_localize("Europe/Berlin"),
                    end=pd.to_datetime("1/08/2018").tz_localize("Europe/Berlin"),
                )
            ],
            "bdate_range": [pd.bdate_range(start="1/1/2018", end="1/08/2018")],
            "period_range": [
                pd.period_range(
                    start=pd.Period("2017Q1", freq="Q"),
                    end=pd.Period("2017Q2", freq="Q"),
                    freq="M",
                )
            ],
            "timedelta_range": [
                pd.timedelta_range("1 Day", periods=3, freq="100000D", unit="s")
            ],
            "interval_range": [
                pd.interval_range(
                    start=pd.Timestamp("2017-01-01"),
                    end=pd.Timestamp("2017-01-04"),
                )
            ],
        }
    ).transpose()
    mo.vstack([mo.plain(date_ranges), date_ranges])
    return


@app.cell
def _(datetime, pd):
    dates_with_null = pd.DataFrame({"mixed": [datetime.now(), None]})
    dates_with_null
    return


if __name__ == "__main__":
    app.run()

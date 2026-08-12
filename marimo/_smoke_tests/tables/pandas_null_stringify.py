import marimo

__generated_with = "0.23.16"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    from datetime import date

    import pandas as pd

    from marimo._plugins.ui._impl.tables.pandas_table import (
        PandasTableManagerFactory,
    )

    return PandasTableManagerFactory, date, json, pd


@app.cell
def _(date, pd):
    dataframe = pd.DataFrame(
        {
            "complex": [
                1 + 2j,
                complex(float("nan"), float("nan")),
            ],
            "timedelta": [pd.Timedelta(days=1), pd.NaT],
            "date": [date(2020, 1, 1), None],
            "bytes": [b"ab", None],
        }
    )
    dataframe["extension"] = pd.Series(
        [(1.0,), None],
        dtype="category",
    )
    dataframe
    return (dataframe,)


@app.cell
def _(PandasTableManagerFactory, dataframe, json):
    manager = PandasTableManagerFactory.create()(dataframe)
    json_data = json.loads(manager.to_json_str())
    json_data
    return


if __name__ == "__main__":
    app.run()

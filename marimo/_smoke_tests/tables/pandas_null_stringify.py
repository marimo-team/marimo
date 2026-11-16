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
def _(PandasTableManagerFactory, dataframe, json, pd):
    manager = PandasTableManagerFactory.create()(dataframe)
    json_data = json.loads(manager.to_json_str())
    assert json_data == [
        {
            "complex": "(1+2j)",
            "timedelta": "1 days 00:00:00",
            "date": "2020-01-01",
            "bytes": "b'ab'",
            "extension": "(1.0,)",
        },
        {
            "complex": None,
            "timedelta": "NaT",
            "date": None,
            "bytes": None,
            "extension": None,
        },
    ]
    strict_json_data = json.loads(manager.to_json_str(strict_json=True))
    assert strict_json_data[1]["timedelta"] is None

    all_null_extension = pd.Series([None], dtype="category").to_frame(
        name="extension"
    )
    all_null_manager = PandasTableManagerFactory.create()(all_null_extension)
    assert all_null_manager.to_json_str(strict_json=False) == (
        '[{"extension":NaN}]'
    )
    assert all_null_manager.to_json_str(strict_json=True) == (
        '[{"extension":null}]'
    )
    json_data
    return


if __name__ == "__main__":
    app.run()

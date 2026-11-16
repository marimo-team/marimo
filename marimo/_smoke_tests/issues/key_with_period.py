# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import pandas as pd

    return mo, pd


@app.cell
def _():
    json_list = [{"key.with.period": "value"} for _ in range(10)]
    return (json_list,)


@app.cell
def _(json_list: list[dict[str, str]], mo):
    mo.ui.table(json_list)


@app.cell
def _(json_list: list[dict[str, str]], mo, pd):
    mo.ui.data_explorer(pd.DataFrame(json_list))


@app.cell
def _(json_list: list[dict[str, str]], mo, pd):
    mo.ui.dataframe(pd.DataFrame(json_list))


if __name__ == "__main__":
    app.run()

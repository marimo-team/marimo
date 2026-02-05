# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "altair",
#     "marimo",
#     "numpy",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(r"""## Data""")
    return


@app.cell
def _():
    import altair as alt
    import numpy as np
    import pandas as pd

    import marimo as mo

    data = {
        "index": np.tile(np.arange(100), 3),
        "value": np.random.randn(300),
        "traces": np.repeat(["Trace 1", "Trace 2", "Trace 3"], 100),
    }

    traces = pd.DataFrame(data)

    print(traces.head())
    return alt, mo, traces


@app.cell
def _(mo):
    mo.md(r"""## Plain Altair""")
    return


@app.cell
def _(alt, traces):
    _brush = alt.selection_interval(encodings=["x"])

    _chart_overview = (
        alt.Chart(traces, height=150, width=550)
        .mark_line()
        .encode(x="index:Q", y="value:Q", color="traces:N")
        .add_params(_brush)
    )

    _chart_detail = (
        alt.Chart(traces)
        .mark_line()
        .encode(x="index:Q", y="value:Q", color="traces:N")
        .transform_filter(_brush)
    )

    _chart_overview | _chart_detail
    return


@app.cell
def _(mo):
    mo.md(r"""## Example of the Or ( | ) operator""")
    return


@app.cell
def _(alt, mo, traces):
    _brush = alt.selection_interval(encodings=["x"])

    chart_overview = mo.ui.altair_chart(
        alt.Chart(traces, height=150, width=550)
        .mark_line()
        .encode(x="index:Q", y="value:Q", color="traces:N")
        .add_params(_brush),
        chart_selection=False,
        legend_selection=False,
    )

    chart_detail = mo.ui.altair_chart(
        alt.Chart(traces)
        .mark_line()
        .encode(x="index:Q", y="value:Q", color="traces:N")
        .transform_filter(_brush),
    )

    chart_overview | chart_detail
    return chart_detail, chart_overview


@app.cell
def _(mo):
    mo.md(r"""## Example of the Or ( | ) operator with selection""")
    return


@app.cell
def _(chart_detail, chart_overview):
    combined = chart_overview | chart_detail
    combined
    return (combined,)


@app.cell
def _(combined):
    combined.value
    return


if __name__ == "__main__":
    app.run()

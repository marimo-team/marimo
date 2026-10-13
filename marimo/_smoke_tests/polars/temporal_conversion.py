# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "polars>=1.9.0",
# ]
# ///

import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl

    return mo, pl


@app.cell
def _(pl):
    events = pl.DataFrame(
        {
            "date_text": ["2026-10-07", "2026-10-08", None],
            "timestamp_text": [
                "2026-10-07 12:34:56.123456",
                "2026-10-08 00:00:00",
                None,
            ],
        }
    )
    return (events,)


@app.cell
def _(mo):
    mo.md("""
    Convert the text columns to **datetime64** in each dataframe below.
    Check that nulls are preserved and fractional seconds remain accurate.
    Run the generated Python code to compare its results with the
    dataframe UI.
    """)
    return


@app.cell
def _(events, mo):
    eager = mo.ui.dataframe(events)
    eager
    return (eager,)


@app.cell
def _(eager):
    eager.value
    return


@app.cell
def _(events, mo):
    lazy = mo.ui.dataframe(events.lazy())
    lazy
    return (lazy,)


@app.cell
def _(lazy):
    lazy.value
    return


if __name__ == "__main__":
    app.run()

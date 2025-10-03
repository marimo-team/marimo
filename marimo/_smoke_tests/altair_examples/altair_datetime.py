import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    from datetime import datetime, timedelta, timezone

    import altair as alt
    import pandas as pd

    import marimo as mo

    df = pd.DataFrame(
        [
            {
                "datetime": datetime.fromtimestamp(i * 10000, timezone.utc),
                "i": i,
                "modulo": i % 10,
            }
            for i in range(1000)
        ]
    )
    return alt, df, mo


@app.cell
def _(alt, df, mo):
    bars = (
        alt.Chart(df)
        .mark_bar()
        .encode(x="datetime:T", y="sum(modulo):Q", color="modulo:Q")
    )
    selection = mo.ui.altair_chart(bars)
    selection
    return (selection,)


@app.cell
def _(selection):
    selection.value
    return


if __name__ == "__main__":
    app.run()

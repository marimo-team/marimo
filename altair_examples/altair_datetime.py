import marimo

__generated_with = "0.9.33"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    import altair as alt
    from datetime import datetime, timezone, timedelta

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
    return alt, datetime, df, mo, pd, timedelta, timezone


@app.cell
def __(alt, df, mo):
    bars = (
        alt.Chart(df)
        .mark_bar()
        .encode(x="datetime:T", y="sum(modulo):Q", color="modulo:Q")
    )
    selection = mo.ui.altair_chart(bars)
    selection
    return bars, selection


@app.cell
def __(selection):
    selection.value
    return


if __name__ == "__main__":
    app.run()

import marimo

__generated_with = "0.12.4"
app = marimo.App()


@app.cell
def _():
    ## BUG: interactive, repeated chart does not work with polars data frame, non interactive one works fine.
    return


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import altair as alt

    from datetime import date

    sample_data = pl.DataFrame(
        {
            "day": [date(2025, 1, 1), date(2025, 1, 2)],
            "value1": [10, 9],
            "value2": [100, 34],
        }
    )
    return alt, date, mo, pl, sample_data


@app.cell
def _(alt, mo, sample_data):
    chart = (
        alt.Chart(sample_data)
        .mark_line()
        .encode(
            x=alt.X("day:T"),
            y=alt.Y(alt.repeat("column"), type="quantitative"),
        )
        .repeat(column=["value1", "value2"])
    )

    # expected output is to have two rows with same charts

    mo.vstack([chart, mo.ui.altair_chart(chart)])
    return (chart,)


if __name__ == "__main__":
    app.run()

import marimo

__generated_with = "0.13.10"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(alt, df):
    _chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("CAST(10 AS DECIMAL(18,3))", type="quantitative", bin=True),
            y=alt.Y("count()", type="quantitative"),
        )
        .properties(width="container")
    )
    _chart
    return


@app.cell
def _():
    import altair as alt
    return (alt,)


@app.cell
def _(mo):
    df = mo.sql(
        f"""
        SELECT
            10::numeric
        """
    )
    return (df,)


if __name__ == "__main__":
    app.run()

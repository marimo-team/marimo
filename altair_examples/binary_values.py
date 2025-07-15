import marimo

__generated_with = "0.11.8"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import altair as alt
    import pandas as pd
    import polars as pl

    df = pd.DataFrame(
        {
            "state": ["000", "010", "100", "111"],
            "count": [1, 2, 3, 4],
            "date": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"],
        }
    )
    pl_df = pl.DataFrame(df)

    pd_chart = (
        alt.Chart(df)
        .mark_line()
        .encode(x="state:O", y="date:T")
        .properties(width=200)
    )
    pl_chart = (
        alt.Chart(pl_df)
        .mark_line()
        .encode(x="state:O", y="date:T")
        .properties(width=200)
    )


    mo.hstack([pd_chart, pl_chart])
    return alt, df, mo, pd, pd_chart, pl, pl_chart, pl_df


@app.cell
def _(alt, mo, pd_chart, pl_chart):
    with alt.data_transformers.enable("marimo_csv"):
        mo.output.append(mo.hstack([pd_chart, pl_chart]))
    return


@app.cell
def _(alt, mo, pd_chart, pl_chart):
    with alt.data_transformers.enable("marimo_json"):
        mo.output.append(mo.hstack([pd_chart, pl_chart]))
    return


@app.cell
def _(alt, mo, pd_chart, pl_chart):
    with alt.data_transformers.enable("marimo_inline_csv"):
        mo.output.append(mo.hstack([pd_chart, pl_chart]))
    return


@app.cell
def _(alt, mo, pd_chart, pl_chart):
    with alt.data_transformers.enable("marimo"):
        mo.output.append(mo.hstack([pd_chart, pl_chart]))
    return


@app.cell
def _(alt, mo, pd_chart, pl_chart):
    # This currently errors since Altair does internal validation, and 'arrow' is not a supported "type"
    with alt.data_transformers.enable("marimo_arrow"):
        mo.output.append(mo.hstack([pd_chart, pl_chart]))
    return


@app.cell
def _(mo, pd_chart, pl_chart):
    mo.hstack([mo.ui.altair_chart(pd_chart), mo.ui.altair_chart(pl_chart)])
    return


if __name__ == "__main__":
    app.run()

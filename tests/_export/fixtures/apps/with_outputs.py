import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    import altair as alt
    import polars as pl

    df = pl.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    chart = alt.Chart(df).mark_point().encode(x="x", y="y")
    mo.ui.altair_chart(chart)
    return alt, chart, df, pl


@app.cell
def _():
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [4, 5, 6])
    plt.gca()
    return ax, fig, plt


@app.cell
def _(mo):
    mo.md("# Hello World")
    return


@app.cell
def _():
    print("hello stdout")
    return


if __name__ == "__main__":
    app.run()

import marimo

__generated_with = "0.8.14"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import altair as alt
    import pandas as pd

    data = pd.DataFrame({"x": range(10), "y": range(10)})

    alt.renderers.set_embed_options(actions=False)
    # altair.renderers.set_embed_options(actions=True)

    # Plain chart
    chart = alt.Chart(data).mark_line().encode(x="x", y="y")
    chart
    return alt, chart, data, mo, pd


@app.cell
def __(chart, mo):
    # Wrapped chart
    mo.ui.altair_chart(chart)
    return


if __name__ == "__main__":
    app.run()

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "pandas==2.2.3",
#     "matplotlib==3.9.2",
#     "altair==5.4.1",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Data Explorer
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    sample = "https://github.com/vega/vega/blob/main/docs/data/stocks.csv"

    mo.md(
        f"""
        This notebook lets you upload a CSV and plot its columns.

        You can download a <a href="{sample}" target="_blank">sample CSV</a> if you'd like.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo, uploaded_file):
    mo.md(
        f"""
        {mo.hstack([mo.md("**Upload a CSV.**")], justify="center")}

        {uploaded_file}
        """
    )
    return


@app.cell
def _(io, mo, pd, uploaded_file):
    mo.stop(not uploaded_file.name())
    df = pd.read_csv(io.StringIO(uploaded_file.contents().decode()))
    return (df,)


@app.cell
def _(df, mo):
    mo.ui.table(df, page_size=5, selection=None)
    return


@app.cell
def _(df, mo):
    plot_type = mo.ui.dropdown(
        ["line", "hist"], value="line", label="Choose a plot type: "
    )

    x_column = mo.ui.dropdown(df.columns, label="Choose x-axis: ")
    y_column = mo.ui.dropdown(df.columns, label="Choose y-axis: ")
    color_column = mo.ui.dropdown(df.columns, label="Choose color-axis: ")
    return color_column, plot_type, x_column, y_column


@app.cell
def _(color_column, mo, plot_type, x_column, y_column):
    mo.hstack(
        [x_column, y_column, color_column, plot_type], justify="space-around"
    ).callout(kind="warn" if not x_column.value else "neutral")
    return


@app.cell
def _(alt, color_column, df, mo, plot_type, x_column, y_column):
    mo.stop(not x_column.value)


    def plot(x_column, y_column, color_column):
        y_column = y_column or "count()"
        title = f"{y_column} by {x_column}"
        encoding = {"x": x_column, "y": y_column}
        if color_column:
            encoding["color"] = color_column
        if plot_type.value == "line":
            chart = alt.Chart(df).mark_line()
        else:
            chart = alt.Chart(df).mark_bar().encode(x=alt.X(x_column, bin=True))
        return chart.encode(**encoding).properties(title=title, width="container")


    plot(x_column.value, y_column.value, color_column.value)
    return


@app.cell
def _(mo):
    uploaded_file = mo.ui.file(filetypes=[".csv"], kind="area")
    return (uploaded_file,)


@app.cell
def _():
    import marimo as mo
    import altair as alt


    import io
    import matplotlib.pyplot as plt
    import pandas as pd

    return alt, io, mo, pd


if __name__ == "__main__":
    app.run()

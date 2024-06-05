# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.14"
app = marimo.App(width="full")


@app.cell
def __():
    import altair as alt
    import marimo as mo
    import pandas as pd
    return alt, mo, pd


@app.cell
def __(pd):
    df = pd.DataFrame(
        data={
            "annotation": ["w", "x", "y", "a", "b", "c", "d", "e", "f", "g"],
            "x": [-3, -2, -1, 0, 1, 2, 3, 4, 5, 6],
            "y": pd.Series(
                [9, 4, 1, 0, 1, 4, 9, 16, 25, 36],
                index=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            ),
        },
        index=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    )
    return df,


@app.cell
def __(alt, df, pd):
    scatter = alt.Chart(df).mark_point().encode(x="x", y="y", tooltip="annotation")
    y_line = (
        alt.Chart(pd.DataFrame({"var1": [0, 0], "var2": [0, 40]}))
        .mark_line(color="grey")
        .encode(alt.X("var1"), alt.Y("var2"))
    )
    return scatter, y_line


@app.cell
def __(alt, mo, scatter, y_line):
    layer_plot = mo.ui.altair_chart(
        alt.layer(scatter, y_line)
        .configure_axis(grid=False)
        .configure_view(strokeWidth=0)
    )

    layer_plot
    return layer_plot,


@app.cell
def __(layer_plot):
    layer_plot.selections
    return


@app.cell
def __(layer_plot):
    print(layer_plot.value)
    return


@app.cell
def __(df, layer_plot):
    print(layer_plot.apply_selection(df))
    # should return a table of selected points based on the scatter plot
    return


if __name__ == "__main__":
    app.run()

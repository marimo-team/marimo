# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="full")


@app.cell
def _():
    import altair as alt
    import marimo as mo
    import pandas as pd
    return alt, mo, pd


@app.cell
def _(pd):
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
    return (df,)


@app.cell
def _(alt, df, pd):
    scatter = alt.Chart(df).mark_point().encode(x="x", y="y", tooltip="annotation")
    y_line = (
        alt.Chart(pd.DataFrame({"var1": [0, 0], "var2": [0, 40]}))
        .mark_line(color="grey")
        .encode(alt.X("var1"), alt.Y("var2"))
    )
    return scatter, y_line


@app.cell
def _(alt, mo, scatter, y_line):
    layer_plot = mo.ui.altair_chart(
        alt.layer(scatter, y_line)
        .configure_axis(grid=False)
        .configure_view(strokeWidth=0)
    )

    layer_plot
    return (layer_plot,)


@app.cell
def _(layer_plot):
    layer_plot.selections
    return


@app.cell
def _(layer_plot):
    print(layer_plot.value)
    return


@app.cell
def _(df, layer_plot):
    print(layer_plot.apply_selection(df))
    # should return a table of selected points based on the scatter plot
    return


if __name__ == "__main__":
    app.run()

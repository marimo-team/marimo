import marimo

__generated_with = "0.18.4"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import numpy as np
    import altair as alt
    return alt, mo, np, pd


@app.cell
def _(np, pd):
    # Create mock data for the heatmap
    np.random.seed(42)
    rows = 10
    cols = 8
    x_labels = [f"X{i}" for i in range(1, cols + 1)]
    y_labels = [f"Y{j}" for j in range(1, rows + 1)]

    data = []
    for y in y_labels:
        for x in x_labels:
            value = np.random.randint(0, 100)
            data.append({"X": x, "Y": y, "Value": value})

    heatmap_df = pd.DataFrame(data)
    heatmap_df
    return (heatmap_df,)


@app.cell
def _(alt, heatmap_df, mo):
    # Create an interactive Altair heatmap with multi-point selection
    selection = alt.selection_point(
        fields=["X", "Y"], bind="legend", toggle=True, clear="click"
    )

    heatmap_chart = (
        alt.Chart(heatmap_df)
        .mark_rect()
        .encode(
            x=alt.X("X:O", title="X Label"),
            y=alt.Y("Y:O", title="Y Label"),
            color=alt.Color("Value:Q", scale=alt.Scale(scheme="viridis")),
            tooltip=["X", "Y", "Value"],
        )
        .add_params(selection)
        .encode(opacity=alt.condition(selection, alt.value(1), alt.value(0.3)))
    )

    heatmap_ui = mo.ui.altair_chart(heatmap_chart)
    heatmap_ui
    return (heatmap_ui,)


@app.cell
def _(heatmap_ui):
    # Display the selected points from the heatmap
    heatmap_ui.value
    return


if __name__ == "__main__":
    app.run()

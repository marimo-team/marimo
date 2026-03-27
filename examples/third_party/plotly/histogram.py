# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
#     "plotly==6.5.1",
# ]
# ///

import marimo

__generated_with = "0.20.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import random

    import marimo as mo
    import plotly.graph_objects as go

    return go, mo, random


@app.cell
def _(mo):
    mo.md("""
    # Reactive Plotly Histograms

    This example demonstrates reactive histogram selections with `mo.ui.plotly`.

    Select bins by dragging a box (or use lasso with Shift). Selections are
    returned to Python as selected rows with `pointIndex` values.
    """)
    return


@app.cell
def _(go, mo, random):
    mo.md("## Numeric Histogram")

    numeric_rng = random.Random(42)
    values = [numeric_rng.gauss(0, 1.0) for _ in range(900)]

    numeric_fig = go.Figure(
        data=go.Histogram(
            x=values,
            nbinsx=28,
            marker_color="#1f77b4",
            opacity=0.85,
            name="numeric",
        )
    )
    numeric_fig.update_layout(
        title="Numeric Histogram",
        xaxis_title="value",
        yaxis_title="count",
        dragmode="select",
    )

    numeric_hist = mo.ui.plotly(numeric_fig)
    numeric_hist
    return numeric_hist, values


@app.cell
def _(numeric_hist, values):
    selected_rows = numeric_hist.value or []

    # Show first selected original values by pointIndex.
    mapped_original_values = [
        values[row["pointIndex"]]
        for row in selected_rows[:10]
        if isinstance(row.get("pointIndex"), int)
    ]
    return mapped_original_values, selected_rows


@app.cell
def _(mapped_original_values, mo, numeric_hist, selected_rows):
    mo.md(f"""
    ### Numeric Selection Output

    **Selected rows:** {len(selected_rows)}

    **Selected indices:** {len(numeric_hist.indices)}

    **Selection range:** {numeric_hist.ranges}

    **First mapped original values (using pointIndex):**
    {mapped_original_values}
    """)
    return


@app.cell
def _(go, mo, random):
    mo.md("## Categorical Histogram")

    categorical_rng = random.Random(7)
    categories = [
        categorical_rng.choice(["A", "B", "C", "D"]) for _ in range(500)
    ]

    categorical_fig = go.Figure(
        data=go.Histogram(
            x=categories,
            marker_color="#2ca02c",
            opacity=0.85,
            name="categorical",
        )
    )
    categorical_fig.update_layout(
        title="Categorical Histogram",
        xaxis_title="category",
        yaxis_title="count",
        dragmode="select",
    )

    categorical_hist = mo.ui.plotly(categorical_fig)
    categorical_hist
    return (categorical_hist,)


@app.cell
def _(categorical_hist, mo):
    mo.md(f"""
    ### Categorical Selection Output

    **Selected rows:** {len(categorical_hist.value)}

    **Selected indices:** {len(categorical_hist.indices)}

    **Selection range:** {categorical_hist.ranges}

    **Preview:**
    {categorical_hist.value[:10]}
    """)
    return


@app.cell
def _(go, mo, random):
    mo.md("## Horizontal Histogram")

    horizontal_rng = random.Random(19)
    y_values = [horizontal_rng.gauss(50, 12) for _ in range(800)]

    horizontal_fig = go.Figure(
        data=go.Histogram(
            y=y_values,
            orientation="h",
            nbinsy=24,
            marker_color="#ff7f0e",
            opacity=0.85,
            name="horizontal",
        )
    )
    horizontal_fig.update_layout(
        title="Horizontal Histogram",
        xaxis_title="count",
        yaxis_title="value",
        dragmode="select",
    )

    horizontal_hist = mo.ui.plotly(horizontal_fig)
    horizontal_hist
    return (horizontal_hist,)


@app.cell
def _(horizontal_hist, mo):
    mo.md(f"""
    ### Horizontal Selection Output

    **Selected rows:** {len(horizontal_hist.value)}

    **Selected indices:** {len(horizontal_hist.indices)}

    **Selection range:** {horizontal_hist.ranges}

    **Preview:**
    {horizontal_hist.value[:10]}
    """)
    return


if __name__ == "__main__":
    app.run()

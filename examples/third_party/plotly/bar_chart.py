# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
#     "plotly==6.5.1",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import plotly.graph_objects as go

    return go, mo


@app.cell
def _(mo):
    mo.md("""
    # Plotly Bar Chart Selection

    This example demonstrates reactive bar chart selections with `mo.ui.plotly`.
    Select bars by clicking or dragging a box to see the selected data.
    """)
    return


@app.cell
def _(go, mo):
    mo.md("## Simple Vertical Bar Chart")

    # Create a simple bar chart with categorical data
    fig_simple = go.Figure(
        data=go.Bar(
            x=["Product A", "Product B", "Product C", "Product D", "Product E"],
            y=[20, 35, 30, 25, 40],
            marker_color="steelblue",
        )
    )

    fig_simple.update_layout(
        title="Sales by Product",
        xaxis_title="Product",
        yaxis_title="Sales ($k)",
    )

    # Wrap with mo.ui.plotly to make it reactive
    bar_chart = mo.ui.plotly(fig_simple)
    return (bar_chart,)


@app.cell
def _(bar_chart, mo):
    mo.md(f"""
    ### Interactive Chart

    {bar_chart}

    ### Selected Bars

    Select bars by dragging a box over them:

    ```python
    {bar_chart.value}
    ```
    """)
    return


@app.cell
def _(go, mo):
    mo.md("## Stacked Bar Chart")

    # Create a stacked bar chart
    fig_stacked = go.Figure()
    fig_stacked.add_trace(
        go.Bar(
            x=["Q1", "Q2", "Q3", "Q4"],
            y=[15, 20, 18, 22],
            name="Product A",
            marker_color="steelblue",
        )
    )
    fig_stacked.add_trace(
        go.Bar(
            x=["Q1", "Q2", "Q3", "Q4"],
            y=[10, 15, 12, 18],
            name="Product B",
            marker_color="lightcoral",
        )
    )

    fig_stacked.update_layout(
        title="Quarterly Sales by Product",
        xaxis_title="Quarter",
        yaxis_title="Sales ($k)",
        barmode="stack",
    )

    stacked_chart = mo.ui.plotly(fig_stacked)
    return (stacked_chart,)


@app.cell
def _(mo, stacked_chart):
    mo.md(f"""
    ### Stacked Bar Chart

    {stacked_chart}

    **Note:** When you select a stacked bar, all segments at that position are returned!

    ### Selected Data

    ```python
    {stacked_chart.value}
    ```
    """)
    return


@app.cell
def _(go, mo):
    mo.md("## Grouped Bar Chart")

    # Create a grouped bar chart
    fig_grouped = go.Figure()
    fig_grouped.add_trace(
        go.Bar(
            x=["Jan", "Feb", "Mar", "Apr"],
            y=[20, 25, 22, 28],
            name="2024",
            marker_color="steelblue",
        )
    )
    fig_grouped.add_trace(
        go.Bar(
            x=["Jan", "Feb", "Mar", "Apr"],
            y=[18, 23, 20, 25],
            name="2025",
            marker_color="lightcoral",
        )
    )

    fig_grouped.update_layout(
        title="Monthly Sales Comparison",
        xaxis_title="Month",
        yaxis_title="Sales ($k)",
        barmode="group",
    )

    grouped_chart = mo.ui.plotly(fig_grouped)
    return (grouped_chart,)


@app.cell
def _(grouped_chart, mo):
    mo.md(f"""
    ### Grouped Bar Chart

    {grouped_chart}

    **Note:** When you select a category, all bars in that group are returned!

    ### Selected Data

    ```python
    {grouped_chart.value}
    ```
    """)
    return


@app.cell
def _(go, mo):
    mo.md("## Horizontal Bar Chart")

    # Create a horizontal bar chart
    fig_horizontal = go.Figure(
        data=go.Bar(
            x=[30, 45, 35, 50, 40],
            y=["Team A", "Team B", "Team C", "Team D", "Team E"],
            orientation="h",
            marker_color="mediumseagreen",
        )
    )

    fig_horizontal.update_layout(
        title="Team Performance",
        xaxis_title="Score",
        yaxis_title="Team",
    )

    horizontal_chart = mo.ui.plotly(fig_horizontal)
    return (horizontal_chart,)


@app.cell
def _(horizontal_chart, mo):
    mo.md(f"""
    ### Horizontal Bar Chart

    {horizontal_chart}

    ### Selected Data

    ```python
    {horizontal_chart.value}
    ```
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## How It Works

    - **Selection**: Drag a box over bars to select them
    - **Categorical axes**: Each bar spans from (index - 0.5) to (index + 0.5)
    - **Stacked/Grouped**: All bars at a position are returned when that position is selected
    - **Data format**: Returns a list of `{"x": value, "y": value, "curveNumber": trace_index}`

    This allows you to build reactive dashboards where selecting bars filters other
    visualizations or displays detailed information about the selected data.
    """)
    return


if __name__ == "__main__":
    app.run()

# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
#     "pandas==2.3.3",
#     "plotly==6.5.1",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Reactive Plotly Line Charts

    Use `mo.ui.plotly` to make line charts reactive. Select data by dragging
    a box on the chart, and get the selected points in Python!
    """)
    return


@app.cell
def _():
    import plotly.graph_objects as go
    import pandas as pd

    return go, pd


@app.cell
def _(pd):
    # Create sample time series data
    data = pd.DataFrame(
        {
            "month": list(range(1, 13)),
            "sales": [45, 52, 48, 65, 72, 68, 80, 85, 78, 90, 95, 88],
            "expenses": [30, 35, 32, 40, 45, 42, 50, 48, 52, 55, 58, 54],
        }
    )
    data
    return (data,)


@app.cell(hide_code=True)
def _(data, go, mo):
    # 1. Simple line chart
    fig1 = go.Figure()
    fig1.add_trace(
        go.Scatter(
            x=data["month"],
            y=data["sales"],
            mode="lines",
            name="Sales",
            line=dict(color="#636EFA", width=2),
        )
    )
    fig1.update_layout(
        title="Monthly Sales", xaxis_title="Month", yaxis_title="Sales ($1000s)"
    )

    line_chart = mo.ui.plotly(fig1)
    line_chart
    return (line_chart,)


@app.cell
def _(line_chart, mo):
    mo.md(f"""
    ## Simple Line Chart

    **Instructions:** Use the box select tool (in the toolbar) to select a range.

    ### Selected Points:
    {line_chart.value}

    ### Selection Range:
    {line_chart.ranges}
    """)
    return


@app.cell(hide_code=True)
def _(data, go, mo):
    # 2. Line chart with markers
    fig2 = go.Figure()
    fig2.add_trace(
        go.Scatter(
            x=data["month"],
            y=data["sales"],
            mode="lines+markers",
            name="Sales",
            line=dict(color="#636EFA", width=2),
            marker=dict(size=8),
        )
    )
    fig2.update_layout(
        title="Monthly Sales (with markers)",
        xaxis_title="Month",
        yaxis_title="Sales ($1000s)",
    )

    line_markers = mo.ui.plotly(fig2)
    line_markers
    return (line_markers,)


@app.cell
def _(line_markers, mo):
    mo.md(f"""
    ## Line Chart with Markers

    **Instructions:** Use the box select tool to select a range.

    ### Selected Points:
    {line_markers.value}
    """)
    return


@app.cell(hide_code=True)
def _(data, go, mo):
    # 3. Multiple lines
    fig3 = go.Figure()
    fig3.add_trace(
        go.Scatter(
            x=data["month"],
            y=data["sales"],
            mode="lines",
            name="Sales",
            line=dict(color="#636EFA", width=2),
        )
    )
    fig3.add_trace(
        go.Scatter(
            x=data["month"],
            y=data["expenses"],
            mode="lines",
            name="Expenses",
            line=dict(color="#EF553B", width=2),
        )
    )
    fig3.update_layout(
        title="Sales vs Expenses",
        xaxis_title="Month",
        yaxis_title="Amount ($1000s)",
    )

    multi_line = mo.ui.plotly(fig3)
    multi_line
    return (multi_line,)


@app.cell
def _(mo, multi_line):
    mo.md(f"""
    ## Multiple Lines

    **Instructions:** Use the box select tool to select a range.
    Points from both lines will be returned!

    ### Selected Points:
    {multi_line.value}

    ### Number of selected points:
    {len(multi_line.value)}
    """)
    return


if __name__ == "__main__":
    app.run()

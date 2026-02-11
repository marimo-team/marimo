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
    # Reactive Plotly Area Charts

    Use `mo.ui.plotly` to make area charts reactive. Select data by dragging
    a box on the chart, and get the selected points in Python!

    Area charts are scatter traces with `fill='tozeroy'` or similar fill options.
    """)
    return


@app.cell
def _():
    import plotly.graph_objects as go
    import pandas as pd

    return go, pd


@app.cell
def _(pd):
    # Create sample data
    data = pd.DataFrame(
        {
            "month": list(range(1, 13)),
            "revenue": [45, 52, 48, 65, 72, 68, 80, 85, 78, 90, 95, 88],
            "costs": [30, 35, 32, 40, 45, 42, 50, 48, 52, 55, 58, 54],
        }
    )
    data
    return (data,)


@app.cell(hide_code=True)
def _(data, go, mo):
    # 1. Basic area chart with fill='tozeroy'
    fig1 = go.Figure()
    fig1.add_trace(
        go.Scatter(
            x=data["month"],
            y=data["revenue"],
            fill="tozeroy",
            mode="lines",
            name="Revenue",
            line=dict(color="#636EFA", width=2),
        )
    )
    fig1.update_layout(
        title="Monthly Revenue (Area Chart)",
        xaxis_title="Month",
        yaxis_title="Revenue ($1000s)",
    )

    area_chart = mo.ui.plotly(fig1)
    area_chart
    return (area_chart,)


@app.cell
def _(area_chart, mo):
    mo.md(f"""
    ## Basic Area Chart (fill='tozeroy')

    **Instructions:** Use the box select tool (in the toolbar) to select a range.

    ### Selected Points:
    {area_chart.value}

    ### Selection Range:
    {area_chart.ranges}

    ### Indices:
    {area_chart.indices}
    """)
    return


@app.cell(hide_code=True)
def _(data, go, mo):
    # 2. Stacked area chart
    fig2 = go.Figure()
    fig2.add_trace(
        go.Scatter(
            x=data["month"],
            y=data["costs"],
            fill="tozeroy",
            stackgroup="one",
            mode="lines",
            name="Costs",
            line=dict(color="#EF553B", width=2),
        )
    )
    fig2.add_trace(
        go.Scatter(
            x=data["month"],
            y=data["revenue"] - data["costs"],
            fill="tonexty",
            stackgroup="one",
            mode="lines",
            name="Profit",
            line=dict(color="#00CC96", width=2),
        )
    )
    fig2.update_layout(
        title="Costs vs Profit (Stacked Area)",
        xaxis_title="Month",
        yaxis_title="Amount ($1000s)",
    )

    stacked_area = mo.ui.plotly(fig2)
    stacked_area
    return (stacked_area,)


@app.cell
def _(mo, stacked_area):
    mo.md(f"""
    ## Stacked Area Chart (stackgroup)

    **Instructions:** Use the box select tool to select a range.
    Points from both areas will be returned!

    ### Selected Points:
    {stacked_area.value}

    ### Number of selected points:
    {len(stacked_area.value)}

    ### Selection Range:
    {stacked_area.ranges}
    """)
    return


if __name__ == "__main__":
    app.run()

# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # DuckDB: Data Export & Integration with Visualization

        This snippet runs an aggregation query using DuckDB and then uses Altair 
        to visualize the results as an interactive bar chart.
        """
    )
    return


@app.cell
def _():
    import pandas as pd
    # Create a sample DataFrame for aggregation
    data = {
        'category': ['A', 'B', 'A', 'B', 'C', 'C'],
        'value': [10, 15, 20, 25, 30, 35]
    }
    df = pd.DataFrame(data)
    return data, df, pd


@app.cell
def _(df, mo):
    agg_df = mo.sql(
        f"""
        SELECT category, AVG(value) as avg_value, COUNT(*) as count
        FROM df
        GROUP BY category
        """
    )
    return (agg_df,)


@app.cell
def _(agg_df):
    # Visualize the aggregated results using Altair
    import altair as alt
    chart = alt.Chart(agg_df).mark_bar().encode(
        x='category:N',
        y='avg_value:Q',
        tooltip=['category', 'avg_value', 'count']
    )
    chart  # Display the chart
    return alt, chart


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

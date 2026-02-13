# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Plotly: Conversion Funnel Analysis

        Create an interactive funnel chart for analyzing conversion steps.
        Common usage: `fig = go.Figure(go.Funnel(y=stages, x=values))`.
        """
    )
    return


@app.cell
def _():
    import plotly.graph_objects as go

    # Sample conversion data
    stages = ['Visitors', 'Cart', 'Checkout', 'Purchase']
    values = [1000, 600, 300, 150]

    # Calculate conversion rates
    rates = [f"{100*v2/v1:.1f}%" 
            for v1, v2 in zip(values[:-1], values[1:])]
    rates = [""] + rates

    # Create funnel chart
    fig = go.Figure(go.Funnel(
        y=stages,
        x=values,
        textinfo="value+percent initial",
        textposition="auto",
        texttemplate="%{value}<br>%{text}",
        text=rates,
        connector={"line": {"color": "royalblue", "dash": "dot"}}
    ))

    # Update layout
    fig.update_layout(
        title="Conversion Funnel Analysis",
        showlegend=False,
        height=500
    )

    fig
    return fig, go, rates, stages, values


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

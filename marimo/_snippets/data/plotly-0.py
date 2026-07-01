# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Plotly: Interactive Line Plot

        Create an interactive line plot with hover tooltips and zoom capabilities. 
        Common usage: `fig = px.line(df, x="x_col", y="y_col")`.
        """
    )
    return


@app.cell
def __():
    import plotly.express as px
    import numpy as np

    # Sample data
    x = np.linspace(0, 10, 100)
    y = np.sin(x)

    # Create interactive plot
    fig = px.line(
        x=x, 
        y=y, 
        title="Interactive Sine Wave",
        labels={"x": "X Axis", "y": "Sin(x)"}
    )

    # Update layout for better appearance
    fig.update_layout(
        showlegend=False,
        hovermode="x unified"
    )

    fig
    return fig, np, px


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()

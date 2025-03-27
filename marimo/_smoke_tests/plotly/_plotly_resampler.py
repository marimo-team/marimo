# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "ipywidgets==8.1.5",
#     "numpy==2.2.3",
#     "pandas==2.2.3",
#     "plotly==5.24.1",
#     "plotly-resampler==0.10.0",
# ]
# ///

import marimo

__generated_with = "0.11.19"
app = marimo.App(width="medium")


@app.cell
def _():
    import numpy as np
    import pandas as pd
    import plotly.express as px
    import ipywidgets
    from plotly_resampler import register_plotly_resampler

    # Register the resampler (using widget mode for interactive performance)
    register_plotly_resampler(mode="widget")

    # Generate 1 million data points
    n_points = 1_000_000
    np.random.seed(42)  # for reproducibility

    # Create a DataFrame with x, y, and color columns
    df = pd.DataFrame(
        {
            "x": np.linspace(0, 100, n_points),
            "y": np.sin(np.linspace(0, 100, n_points))
            + np.random.normal(0, 0.5, n_points),
            "color": np.random.choice(["A", "B", "C"], n_points),
        }
    )

    # Create a scatter plot with Plotly Express
    fig = px.scatter(
        df, x="x", y="y", color="color", title="Scatter Plot with 1M Datapoints"
    )

    fig
    return df, fig, ipywidgets, n_points, np, pd, px, register_plotly_resampler


if __name__ == "__main__":
    app.run()

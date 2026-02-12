# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "anywidget==0.9.21",
#     "ipywidgets==8.1.8",
#     "marimo",
#     "numpy==2.4.2",
#     "pandas==3.0.0",
#     "plotly==6.5.2",
#     "plotly-resampler==0.11.0",
#     "pytz==2025.2",
# ]
# ///

import marimo

__generated_with = "0.19.11"
app = marimo.App(width="medium")


@app.cell
def _():
    import numpy as np
    import pandas as pd
    import plotly.express as px
    import ipywidgets
    import anywidget
    from plotly_resampler import register_plotly_resampler

    # Register the resampler (using widget mode for interactive performance)
    register_plotly_resampler(mode="widget")

    # Generate 1 million data points
    n_points = 10_000_000
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
    return


if __name__ == "__main__":
    app.run()

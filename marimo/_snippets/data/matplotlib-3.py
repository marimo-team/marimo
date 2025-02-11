# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Matplotlib: Time Series with Custom Formatting

        Create time series visualizations with `plot_date()` and custom date formatting. 
        Shows rolling averages and confidence intervals using `fill_between()`.
        """
    )
    return


@app.cell
def _():
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    return np, pd, plt


@app.cell
def _(np, pd, plt):
    def create_time_series_plot():
        # Generate sample time series data
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        np.random.seed(42)
        values = np.random.randn(100).cumsum()

        # Calculate rolling statistics
        window = 20
        rolling_mean = pd.Series(values).rolling(window=window).mean()
        rolling_std = pd.Series(values).rolling(window=window).std()

        # Create the plot
        fig, ax = plt.subplots(figsize=(12, 6))

        # Plot raw data and rolling mean
        ax.plot(dates, values, 'k-', alpha=0.3, label='Raw Data')
        ax.plot(dates, rolling_mean, 'b-', label=f'{window}-Day Mean')

        # Add confidence interval
        ax.fill_between(dates, 
                       rolling_mean - 2*rolling_std,
                       rolling_mean + 2*rolling_std,
                       color='b', alpha=0.1, label='95% Confidence')

        # Customize the plot
        ax.set_title('Time Series with Rolling Statistics')
        ax.set_xlabel('Date')
        ax.set_ylabel('Value')
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend()

        # Format date axis
        plt.gcf().autofmt_xdate()

        return ax

    create_time_series_plot()
    return (create_time_series_plot,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

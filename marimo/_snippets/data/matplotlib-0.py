# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Matplotlib: Basic Line and Scatter Plots

        Create basic plots using `plt.plot()` and `plt.scatter()`. Shows line styles, 
        markers, and colors with `plt.legend()` for multiple series.
        """
    )
    return


@app.cell
def _():
    import matplotlib.pyplot as plt
    import numpy as np
    return np, plt


@app.cell
def _(np, plt):
    def create_line_scatter_plot():
        # Generate sample data
        x = np.linspace(0, 10, 100)
        y1 = np.sin(x)
        y2 = np.cos(x)

        # Create figure and axis
        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot multiple lines with different styles
        ax.plot(x, y1, 'b-', label='sin(x)', linewidth=2)
        ax.scatter(x[::10], y2[::10], c='r', label='cos(x)', s=50)

        # Customize the plot
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_title('Basic Line and Scatter Plot')
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend()

        return ax

    create_line_scatter_plot()
    return (create_line_scatter_plot,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

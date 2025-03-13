# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Matplotlib: Multiple Subplots Layout

        Create multiple subplots using `plt.subplots()`. Common for comparing different 
        views of data with `sharex` and `sharey` options.
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
    def create_multi_subplot():
        # Generate sample data
        x = np.linspace(0, 10, 100)
        y1 = np.sin(x)
        y2 = np.exp(-x/3)

        # Create figure with 2x2 subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 8))

        # Plot different visualizations
        ax1.plot(x, y1, 'b-', label='Sine')
        ax1.set_title('Line Plot')
        ax1.legend()

        ax2.scatter(x[::5], y2[::5], c='r', s=50, alpha=0.5)
        ax2.set_title('Scatter Plot')

        ax3.fill_between(x, y1, alpha=0.3)
        ax3.set_title('Area Plot')

        ax4.hist(y2, bins=20, alpha=0.7)
        ax4.set_title('Histogram')

        # Adjust layout
        plt.tight_layout()

        return ax1, ax2, ax3, ax4

    create_multi_subplot()
    return (create_multi_subplot,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

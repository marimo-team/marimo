# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Matplotlib: Advanced Subplot Layouts

        Different subplot arrangements using `GridSpec` and `subplot2grid`. 
        Shows uneven layouts and spanning multiple grid cells.
        """
    )
    return


@app.cell
def _():
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    import numpy as np
    return gridspec, np, plt


@app.cell
def _(gridspec, np, plt):
    def create_advanced_subplots():
        # Create figure with GridSpec
        fig = plt.figure(figsize=(12, 8))
        gs = gridspec.GridSpec(3, 3)

        # Spanning multiple cells
        ax1 = fig.add_subplot(gs[0, :])  # Span all columns
        ax2 = fig.add_subplot(gs[1:, 0:2])  # Span 2 rows, 2 columns
        ax3 = fig.add_subplot(gs[1:, 2])  # Span 2 rows, 1 column

        # Add sample plots
        x = np.linspace(0, 10, 100)
        ax1.plot(x, np.sin(x))
        ax2.scatter(x[::5], np.cos(x[::5]))
        ax3.hist(np.random.randn(100))

        plt.tight_layout()

        return ax1, ax2, ax3

    create_advanced_subplots()
    return (create_advanced_subplots,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

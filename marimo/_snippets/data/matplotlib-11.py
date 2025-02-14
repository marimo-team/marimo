# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Matplotlib: Legend Customization and Styling

        Customize legend placement, styling, and handles. 
        Shows common legend patterns in data visualization.
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
    def create_advanced_legend():
        # Generate data
        x = np.linspace(0, 10, 100)
        y1 = np.sin(x)
        y2 = np.cos(x)

        # Create plot with custom legend
        fig, ax = plt.subplots(figsize=(8, 5))

        # Multiple plot types
        line1 = ax.plot(x, y1, 'b-', label='Sine')[0]
        scatter = ax.scatter(x[::10], y2[::10], c='r', label='Cosine')

        # Custom legend
        ax.legend(
            [line1, scatter],
            ['Sin(x)', 'Cos(x)'],
            loc='upper right',
            bbox_to_anchor=(1.15, 1),
            frameon=True,
            fancybox=True,
            shadow=True
        )

        return ax

    create_advanced_legend()
    return (create_advanced_legend,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

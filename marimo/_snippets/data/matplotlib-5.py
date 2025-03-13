# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Matplotlib: Data Point Labels and Explanatory Notes

        Add annotations using `annotate()` and text using `text()`. 
        Common for highlighting specific data points and adding explanations.
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
    def create_annotated_plot():
        # Create data
        x = np.linspace(0, 10, 20)
        y = np.sin(x)

        # Create plot with annotations
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(x, y, 'b-')

        # Add arrow annotation
        ax.annotate('Maximum', 
                    xy=(4.7, 1.0),        # Point to annotate
                    xytext=(5.5, 0.5),    # Text position
                    arrowprops=dict(facecolor='black', shrink=0.05))

        # Add text box
        ax.text(2, -0.5, 'Sine Wave', 
                bbox=dict(facecolor='white', alpha=0.7))

        return ax

    create_annotated_plot()
    return (create_annotated_plot,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

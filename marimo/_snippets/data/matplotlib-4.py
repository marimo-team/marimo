# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Matplotlib: Styling and Themes

        Apply custom styles using `plt.style.use()` and customize plots with 
        `rcParams`. Common for creating publication-quality figures.
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
    def create_styled_plot():
        # Set style and custom parameters
        plt.style.use('ggplot')  # Using built-in ggplot style
        plt.rcParams['figure.figsize'] = [8, 5]
        plt.rcParams['axes.grid'] = True

        # Generate sample data
        x = np.linspace(0, 10, 50)
        y = np.sin(x) + np.random.normal(0, 0.2, 50)

        # Create styled plot
        fig, ax = plt.subplots()
        ax.scatter(x, y, c='crimson', alpha=0.6)
        ax.set_title('Styled Scatter Plot', fontsize=12, pad=10)

        # Add minimal styling
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        return ax

    create_styled_plot()
    return (create_styled_plot,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

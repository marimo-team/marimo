# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Matplotlib: Statistical Visualizations

        Create statistical plots using `hist()`, `boxplot()`, and `violinplot()`. 
        Common for data distribution analysis with customizable bins and orientations.
        """
    )
    return


@app.cell
def _():
    import matplotlib.pyplot as plt
    import numpy as np

    # Generate sample data
    np.random.seed(42)
    data1 = np.random.normal(100, 10, 200)
    data2 = np.random.normal(90, 20, 200)
    data = [data1, data2]

    # Create figure with three subplots
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))

    # Histogram
    ax1.hist(data1, bins=30, alpha=0.7, color='skyblue', label='Distribution 1')
    ax1.hist(data2, bins=30, alpha=0.7, color='lightgreen', label='Distribution 2')
    ax1.set_title('Histogram')
    ax1.legend()

    # Box Plot
    ax2.boxplot(data, labels=['Dist 1', 'Dist 2'])
    ax2.set_title('Box Plot')

    # Violin Plot
    ax3.violinplot(data)
    ax3.set_title('Violin Plot')
    ax3.set_xticks([1, 2])
    ax3.set_xticklabels(['Dist 1', 'Dist 2'])

    plt.tight_layout()
    plt.gca()
    return ax1, ax2, ax3, data, data1, data2, fig, np, plt


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

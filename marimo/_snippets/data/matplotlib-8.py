# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Matplotlib: Error Bars

        Add error bars using `errorbar()`. Common in scientific visualization 
        to show measurement uncertainty or variation in data.
        """
    )
    return


@app.cell
def _():
    import matplotlib.pyplot as plt
    import numpy as np

    # Create sample data with errors
    x = np.linspace(0, 10, 5)
    y = np.exp(-x/2)
    y_err = 0.1 + 0.1*np.random.rand(len(x))

    # Create error bar plot
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(x, y, yerr=y_err, fmt='o-', capsize=5,
                ecolor='gray', markersize=8)

    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.grid(True, linestyle='--', alpha=0.7)
    plt.gca()
    return ax, fig, np, plt, x, y, y_err


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

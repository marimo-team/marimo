import marimo

__generated_with = "0.17.7"
app = marimo.App(width="medium")


@app.cell
def _():
    return


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    return np, plt


@app.cell
def _(np, plt):
    # Test from the original issue
    x = np.random.rand(27)
    y = 20 - np.linspace(2, 20, 27) * x

    plt.figure(figsize=(6, 4))
    plt.scatter(x, y)
    plt.title("Retina Test - Should be crisp!")
    plt.xlabel("X values")
    plt.ylabel("Y values")
    plt.gca()
    return


@app.cell
def _(plt):
    # Another test with a line plot
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot([1, 2, 3, 4], [1, 4, 2, 3], marker="o", linestyle="-", linewidth=2)
    ax.set_title("Line Plot - Retina Test")
    ax.grid(True)
    fig
    return


if __name__ == "__main__":
    app.run()

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return


@app.cell
def _():
    import matplotlib.pyplot as plt
    import numpy as np

    x = np.linspace(0, 1, 100)
    y = np.sin(x)

    plt.plot(x, y)
    plt.title("Sine Wave")
    plt.xlabel("x")
    plt.ylabel("sin(x)")

    plt.gca()
    return


if __name__ == "__main__":
    app.run()

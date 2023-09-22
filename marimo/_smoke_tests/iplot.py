import marimo

__generated_with = "0.1.15"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import numpy as np
    import matplotlib.pyplot as plt
    # import matplotlib
    # matplotlib.use('WebAgg')
    return mo, np, plt


@app.cell
def __(mo, np, plt):
    # Generating random data
    np.random.seed(42)
    x = np.random.randint(0, 100, size=100)
    y = np.random.randint(0, 100, size=100)
    z = np.random.randint(0, 100, size=100)

    # Creating a 3D scatter plot
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.scatter(x, y, z, c='r', marker='o')

    ax.set_xlabel('X Label')
    ax.set_ylabel('Y Label')
    ax.set_zlabel('Z Label')

    mo.mpl_interactive(fig)
    return ax, fig, x, y, z


if __name__ == "__main__":
    app.run()

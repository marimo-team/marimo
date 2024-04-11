# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.10"
app = marimo.App()


@app.cell
def __():
    import matplotlib.pyplot as plt
    import numpy as np

    plt.plot(np.arange(52))

    # better to do plt.gca(), but discovered this translating script
    plt.show()
    return np, plt


if __name__ == "__main__":
    app.run()

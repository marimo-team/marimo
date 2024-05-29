# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.6.11"
app = marimo.App()


@app.cell
def __():
    import matplotlib.pyplot as plt
    plt.plot([1, 2])
    plt.legend(["asdf"], bbox_to_anchor=(1.2, 0.5))
    return plt,


@app.cell
def __(plt):
    plt.plot([1, 2])
    plt.legend(["asdf"], bbox_to_anchor=(1.2, 0.5))
    plt.show()
    return


@app.cell
def __():
    import matplotlib
    backend = matplotlib.get_backend()
    backend
    return backend, matplotlib


if __name__ == "__main__":
    app.run()

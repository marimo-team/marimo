# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import matplotlib.pyplot as plt
    plt.plot([1, 2])
    plt.legend(["asdf"], bbox_to_anchor=(1.2, 0.5))
    return (plt,)


@app.cell
def _(plt):
    plt.plot([1, 2])
    plt.legend(["asdf"], bbox_to_anchor=(1.2, 0.5))
    plt.show()
    return


@app.cell
def _():
    import matplotlib
    backend = matplotlib.get_backend()
    backend
    return


if __name__ == "__main__":
    app.run()

# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.77"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    # import pdb; pdb.set_trace()
    mo.pdb.set_trace()
    return


if __name__ == "__main__":
    app.run()

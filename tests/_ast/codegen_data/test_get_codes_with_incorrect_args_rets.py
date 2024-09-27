import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def one():
    import numpy as np


@app.cell
def two():
    x = 0
    xx = 1
    return (x,)


@app.cell
def three():
    y = x + 1


@app.cell
def four(y):
    # comment
    z = np.array(x + y)
    return (z,)


@app.cell
def five():
    # just a comment
    ...


if __name__ == "__main__":
    app.run()

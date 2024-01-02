import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def one():
    import numpy as np
    return np,


@app.cell
def two():
    x = 0
    xx = 1
    return x, xx


@app.cell
def three(x):
    y = x + 1
    return y,


@app.cell
def four(np, x, y):
    # comment
    z = np.array(x + y)
    return z,


@app.cell
def five():
    # just a comment
    return


if __name__ == "__main__":
    app.run()

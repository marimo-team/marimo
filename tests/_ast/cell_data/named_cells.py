import marimo

__generated_with = "0.2.8"
app = marimo.App()


@app.cell
def f():
    x = 0
    return (x,)


@app.cell
def g(x):
    y = x + 1
    return (y,)


@app.cell
def h(y):
    z = y + 1
    z
    return (z,)


if __name__ == "__main__":
    app.run()

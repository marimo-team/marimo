import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _(y):
    x = y
    return (x,)


@app.cell
def _(x):
    y = x
    return (y,)


if __name__ == "__main__":
    app.run()

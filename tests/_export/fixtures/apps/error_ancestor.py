import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _():
    raise ValueError("ancestor error")


@app.cell
def _(x):
    y = x + 1
    return (y,)


if __name__ == "__main__":
    app.run()

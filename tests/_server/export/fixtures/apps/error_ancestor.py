import marimo

__generated_with = "0.23.2"
app = marimo.App()


@app.cell
def _():
    raise ValueError("ancestor error")
    return


@app.cell
def _(x):
    y = x + 1
    return


if __name__ == "__main__":
    app.run()

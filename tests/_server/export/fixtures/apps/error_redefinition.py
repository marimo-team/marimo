import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _():
    x = 1
    return (x,)


@app.cell
def _():
    x = 2  # Redefines x
    return (x,)


if __name__ == "__main__":
    app.run()

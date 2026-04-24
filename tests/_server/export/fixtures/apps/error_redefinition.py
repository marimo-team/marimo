import marimo

__generated_with = "0.23.2"
app = marimo.App()


@app.cell
def _():
    x = 1
    return


@app.cell
def _():
    x = 2  # Redefines x
    return


if __name__ == "__main__":
    app.run()

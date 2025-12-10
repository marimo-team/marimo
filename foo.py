import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell
def _():
    10
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()

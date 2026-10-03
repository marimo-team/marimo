import marimo

__generated_with = "0.25.1"
app = marimo.App()


@app.cell
def _():
    import math
    THRESHOLD = 10
    return THRESHOLD, math


if __name__ == "__main__":
    app.run()

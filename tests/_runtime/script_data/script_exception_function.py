import marimo

__generated_with = "0.6.19"
app = marimo.App()


@app.function
def bad_divide(y: int) -> int:
    return y / 0


@app.cell
def _():
    x = bad_divide(100)
    return (x,)


if __name__ == "__main__":
    app.run()

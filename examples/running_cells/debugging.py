import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.function
def foo(x):
    breakpoint()
    return 1 / x


@app.cell
def _():
    foo(1)
    return


if __name__ == "__main__":
    app.run()

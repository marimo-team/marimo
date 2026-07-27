import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _():
    x = undefined_variable  # noqa: F821
    return (x,)


if __name__ == "__main__":
    app.run()

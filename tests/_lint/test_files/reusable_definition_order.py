import marimo

__generated_with = "0.18.0"
app = marimo.App()


@app.function
def uses_offset(x: int = offset()) -> int:
    return x + 1


@app.cell
def _():
    scale = 2
    return (scale,)


@app.cell
def _(scale):
    def local_only(x: int = scale) -> int:
        return x + 1

    return


@app.function
def offset() -> int:
    return 1


if __name__ == "__main__":
    app.run()

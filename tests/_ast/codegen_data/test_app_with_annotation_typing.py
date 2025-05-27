import marimo

__generated_with = "0.0.0"
app = marimo.App(width="medium")

with app.setup:
    CONSTANT: int = 42


@app.cell
def _():
    z: "int" = 0
    return (z,)


@app.cell
def _():
    x: int = CONSTANT + 2
    y: float = 2.0
    return x, y


@app.cell
def _(x: int, y: float, z: "int"):
    _ = x + y + z
    return


if __name__ == "__main__":
    app.run()

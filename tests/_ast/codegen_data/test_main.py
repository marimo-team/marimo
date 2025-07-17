import marimo

__generated_with = "0.14.11"
app = marimo.App()


@app.cell
def one():
    x: int = 0
    return (x,)


@app.cell
def two(x: int):
    y: int = x + 1
    z: int = y + 1
    "z"
    return (y,)


@app.cell
def three(x: int, y: int):
    a: int = x + y
    return


if __name__ == "__main__":
    app.run()

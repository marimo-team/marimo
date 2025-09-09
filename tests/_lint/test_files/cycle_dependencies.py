import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __():
    x = 1 + z  # This should trigger MR002 - cycle dependency
    return (x,)


@app.cell
def __():
    y = x + 1
    return (y,)


@app.cell
def __():
    z = y + 1
    return (z,)


if __name__ == "__main__":
    app.run()

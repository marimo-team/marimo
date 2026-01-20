import marimo

app = marimo.App()


@app.cell
def __():
    x = 1
    return (x,)


@app.cell
def __():
    x = 2
    return (x,)


if __name__ == "__main__":
    app.run()

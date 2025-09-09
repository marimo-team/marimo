import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __():
    print(1)
    x = 1
    return (x,)


@app.cell
def __():
    x = 2  # This should trigger MR001 - multiple definitions
    return (x,)


if __name__ == "__main__":
    app.run()

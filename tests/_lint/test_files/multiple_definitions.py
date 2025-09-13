import marimo

__generated_with = "0.15.2"
app = marimo.App()


@app.cell
def _():
    print(1)
    x = 1
    return


@app.cell
def _():
    x = 2  # This should trigger MR001 - multiple definitions
    return


if __name__ == "__main__":
    app.run()

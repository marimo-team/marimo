import marimo

__generated_with = "0.23.2"
app = marimo.App()


@app.cell
def _():
    print("hello before error")
    raise ValueError("test error")
    return


if __name__ == "__main__":
    app.run()

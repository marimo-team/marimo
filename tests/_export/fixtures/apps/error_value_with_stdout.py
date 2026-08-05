import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _():
    print("hello before error")
    raise ValueError("test error")


if __name__ == "__main__":
    app.run()

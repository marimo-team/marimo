import marimo

__generated_with = "0.0.1"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    mo.md("# Hello Marimo!")
    return mo,


if __name__ == "__main__":
    app.run()

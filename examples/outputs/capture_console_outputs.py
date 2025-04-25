import marimo

__generated_with = "0.12.9"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    with mo.capture_stdout() as output:
        print("Hello, world")

    mo.md(output.getvalue())
    return (output,)


if __name__ == "__main__":
    app.run()

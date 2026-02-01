import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    print("This is a console output")
    print("Notice that it's below the cell.")
    print("You can configure where outputs show up in your user configuration.")

    mo.md(
        "This is a cell output. Console outputs show up below a cell; cell outputs show up above."
    )
    return


if __name__ == "__main__":
    app.run()

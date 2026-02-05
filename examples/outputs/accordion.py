import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.accordion(
        {
            "Door 1": mo.md("Nothing!"),
            "Door 2": mo.md("Nothing!"),
            "Door 3": mo.md(
                "![goat](https://images.unsplash.com/photo-1524024973431-2ad916746881)"
            ),
        }
    )
    return


if __name__ == "__main__":
    app.run()

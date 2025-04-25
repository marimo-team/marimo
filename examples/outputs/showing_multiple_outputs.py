import marimo

__generated_with = "0.12.9"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    for i in range(3):
        mo.output.append(mo.md(f"$i = {i}$"))

    mo.output.append(mo.md("Completed iteration."))
    return (i,)


if __name__ == "__main__":
    app.run()

import marimo

__generated_with = "0.17.4"
app = marimo.App(width="medium")


@app.cell
def _():
    return


@app.cell
def _(mo):
    a=mo.ui.table({"a":[1,2,3]},selection="single",initial_selection=[0])
    a
    return (a,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(a, mo):
    md = mo.md(f"$a={a.value["a"][0]}$")
    md
    return


if __name__ == "__main__":
    app.run()

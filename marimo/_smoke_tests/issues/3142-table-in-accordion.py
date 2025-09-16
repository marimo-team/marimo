import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    table=mo.ui.table([{"col1": "hello"},{"col1": "world"}], selection="single")
    return (table,)


@app.cell
def _(mo, table):
    if table.value:
        val = table.value[0]["col1"]
    else:
        val = ""
    text=mo.ui.text(label="Select from table", value=val)
    return (text,)


@app.cell
def _(mo, table, text):
    mo.accordion({"fold down": mo.vstack([table, text])})
    return


if __name__ == "__main__":
    app.run()

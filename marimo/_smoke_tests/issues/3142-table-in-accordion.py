
import marimo

__generated_with = "0.9.34"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return (mo,)


@app.cell
def __(mo):
    table=mo.ui.table([{"col1": "hello"},{"col1": "world"}], selection="single")
    return (table,)


@app.cell
def __(mo, table):
    if table.value:
        val = table.value[0]["col1"]
    else:
        val = ""
    text=mo.ui.text(label="Select from table", value=val)

    return text, val


@app.cell
def __(mo, table, text):
    mo.accordion({"fold down": mo.vstack([table, text])})
    return


if __name__ == "__main__":
    app.run()

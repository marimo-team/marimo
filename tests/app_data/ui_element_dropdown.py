import marimo as mo

app = mo.App()

@app.cell
def __():
    import marimo as mo
    d = mo.ui.dropdown(options=["first", "second"], value="first")
    return d,

@app.cell
def __(d):
    f"value is {d.value}"

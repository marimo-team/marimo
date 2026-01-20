import marimo

app = marimo.App()


@app.cell
def __(mo):
    control_dep = None
    mo.md("markdown")
    return control_dep


@app.cell
def __(mo, control_dep):
    control_dep
    mo.md(f"parameterized markdown {123}")
    return


@app.cell
def __():
    mo.md("plain markdown")
    return (mo,)


@app.cell
def __():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

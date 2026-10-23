import marimo

__generated_with = "0.25.1"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    slider = mo.ui.slider(0, 10, 1, 3, label="A slider")
    slider
    return (slider,)


@app.cell
def _(slider):
    value = slider.value
    label = "our"
    return label, value


@app.cell
def _():
    kind = "info"
    return (kind,)


@app.cell
def _(kind: str, label: str, mo, value: int | float):
    mo.callout(
        mo.md(f"""
        The value of *{label}* slider is **{value}**!
        """), kind
    )
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()

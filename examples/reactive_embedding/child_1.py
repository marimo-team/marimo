import marimo

__generated_with = "0.17.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(parent):
    try:
        _parent = parent
    except NameError:
        _parent = None
    x_from_parent = getattr(_parent, "x", "〈not provided〉")
    return (x_from_parent,)


@app.cell
def _(mo):
    slider = mo.ui.slider(0, 20, 1, label="**child_1.v**")
    return (slider,)


@app.cell
def _(slider):
    v = slider.value
    return (v,)


@app.cell
def _(mo, v, x_from_parent):
    msg = mo.md(f"""
    - I see **parent.x = {x_from_parent}
    - My v = {v}
    """)
    return (msg,)


@app.cell
def _(mo, msg, slider):
    mo.callout(
        mo.vstack([
            mo.md("### Child 1"),
            msg,
            slider,
        ])
    )
    return


if __name__ == "__main__":
    app.run()

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import panel as pn

    pn.extension("vega")
    return (pn,)


@app.cell
def _(pn):
    slider = pn.widgets.IntSlider(start=0, end=10, value=5)

    slider.rx() * "🚀"
    return (slider,)


@app.cell
def _(pn, slider):
    pn.Column(slider, pn.pane.Markdown("🚀"))
    return


@app.cell
def _(pn):
    [
        pn.widgets.FloatSlider(value=3.14),
        pn.widgets.Select(
            options=[
                {"label": "Option 1", "value": 1},
                {"label": "Option 2", "value": 2},
            ]
        ),
        pn.widgets.Checkbox(name="Check me"),
        pn.widgets.DatePicker(),
        pn.widgets.FileInput(multiple=True),
    ]
    return


if __name__ == "__main__":
    app.run()

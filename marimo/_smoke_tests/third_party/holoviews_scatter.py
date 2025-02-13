# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "bokeh==3.6.2",
#     "hvplot==0.11.2",
#     "marimo",
#     "panel==1.5.5",
# ]
# ///

import marimo

__generated_with = "0.11.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import hvplot.pandas
    import panel

    from bokeh.sampledata.iris import flowers as df

    df.sample(n=5)

    df.hvplot.scatter(
        x="sepal_length",
        y="sepal_width",
        by="species",
        legend="top",
        height=400,
        width=400,
    )
    return df, hvplot, panel


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.ui.panel({1: 2})
    return


@app.cell
def _(mo):
    import panel as pn

    slider = pn.widgets.IntSlider(start=0, end=10, value=5)
    rx_stars = mo.ui.panel(slider.rx() * "*")
    rx_stars
    return pn, rx_stars, slider


if __name__ == "__main__":
    app.run()

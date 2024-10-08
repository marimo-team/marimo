

import marimo

__generated_with = "0.8.22"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import plotly.express as px

    df = px.data.tips()
    mo.md("# Plotly Selection")
    return df, mo, px


@app.cell
def __(df):
    df
    return


@app.cell
def __(df, mo, px):
    _fig = px.treemap(df, path=[px.Constant("all"), 'day', 'time', 'sex'], values='total_bill')
    plot = mo.ui.plotly(_fig)
    return (plot,)


@app.cell
def __(mo, plot):
    mo.vstack([plot], align="stretch")
    return


@app.cell
def __(plot):
    plot.value
    return


@app.cell
def __(mo, px):
    _data = dict(
        character=["Eve", "Cain", "Seth", "Enos", "Noam", "Abel", "Awan", "Enoch", "Azura"],
        parent=["", "Eve", "Eve", "Seth", "Seth", "Eve", "Eve", "Awan", "Eve" ],
        value=[10, 14, 12, 10, 2, 6, 6, 4, 4])

    sunburst = mo.ui.plotly(px.sunburst(
        _data,
        names='character',
        parents='parent',
        values='value',
    ))

    sunburst
    return (sunburst,)


@app.cell
def __(sunburst):
    sunburst.value
    return


if __name__ == "__main__":
    app.run()

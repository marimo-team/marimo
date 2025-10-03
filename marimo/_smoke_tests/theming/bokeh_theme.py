# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "bokeh",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    from bokeh.plotting import figure, show
    from bokeh.io import curdoc
    return curdoc, figure


@app.cell
def _(curdoc, figure):
    fruits = ['Apples', 'Pears', 'Nectarines', 'Plums', 'Grapes', 'Strawberries']
    counts = [5, 3, 4, 2, 4, 6]

    curdoc().theme = None

    p = figure(x_range=fruits, height=350, title="Fruit Counts",
               toolbar_location=None, tools="")

    p.vbar(x=fruits, top=counts, width=0.9)

    p.xgrid.grid_line_color = None
    p.y_range.start = 0
    p
    return counts, fruits


@app.cell
def _(counts, curdoc, figure, fruits):
    curdoc().theme = "light_minimal"

    p3 = figure(x_range=fruits, height=350, title="Fruit Counts",
               toolbar_location=None, tools="")

    p3.vbar(x=fruits, top=counts, width=0.9)

    p3.xgrid.grid_line_color = None
    p3.y_range.start = 0
    p3
    return


@app.cell
def _(counts, curdoc, figure, fruits):
    curdoc().theme = "dark_minimal"

    p2 = figure(x_range=fruits, height=350, title="Fruit Counts",
               toolbar_location=None, tools="")

    p2.vbar(x=fruits, top=counts, width=0.9)

    p2.xgrid.grid_line_color = None
    p2.y_range.start = 0
    p2
    return


if __name__ == "__main__":
    app.run()

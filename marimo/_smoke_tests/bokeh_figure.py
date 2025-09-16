# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "bokeh==3.6.3",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import bokeh
    return


@app.cell
def _():
    from bokeh.plotting import figure, show, output_notebook
    # NOOP in marimo
    output_notebook()
    return figure, show


@app.cell
def _(figure):
    p = figure()
    # Shows GlyphRenderer
    p.scatter([1, 2], [3, 4])
    return (p,)


@app.cell
def _(p, show):
    show(p)
    return


@app.cell
def _(p):
    # Shows plot
    p
    return


if __name__ == "__main__":
    app.run()

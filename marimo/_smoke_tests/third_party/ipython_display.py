# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "ipython",
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import IPython
    import marimo as mo

    url = IPython.display.HTML("https://marimo.io")
    url
    return IPython, url


@app.cell
def _(IPython):
    html = IPython.display.HTML("<em>hello world</em>")
    html
    return (html,)


@app.cell
def _(IPython, html, url):
    IPython.display.display(html, url)
    return


@app.cell
def _():
    # not on PyPI
    # installation instructions here https://github.com/allefeld/pytikz
    import tikz
    return (tikz,)


@app.cell
def _(tikz):
    # define coordinates as a list of tuples
    coords = [(0, 0), (0, 2), (1, 3.25), (2, 2), (2, 0), (0, 2), (2, 2), (0, 0), (2, 0)]

    # create `Picture` object
    pic = tikz.Picture()
    # draw a line following the coordinates
    pic.draw(tikz.line(coords), thick=True, rounded_corners='4pt')
    return (pic,)


@app.cell
def _(pic):
    pic.demo(dpi=300)
    return


if __name__ == "__main__":
    app.run()

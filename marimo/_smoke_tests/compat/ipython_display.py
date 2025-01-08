# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "ipython==8.31.0",
# ]
# ///

import marimo

__generated_with = "0.10.9"
app = marimo.App(width="medium")


@app.cell
def _():
    from IPython.display import SVG, Markdown, display
    return Markdown, SVG, display


@app.cell
def _(SVG):
    svg = SVG(
        '<svg height="100" width="100"><circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" /></svg>'
    )
    svg
    return (svg,)


@app.cell
def _(Markdown):
    markdown = Markdown(
        "## This is a Markdown Example\nHere is a list:\n- Item 1\n- Item 2\n- Item 3"
    )
    markdown
    return (markdown,)


@app.cell
def _(display, markdown, svg):
    display(markdown)
    display(svg)  # does not work, not sure why
    return


if __name__ == "__main__":
    app.run()

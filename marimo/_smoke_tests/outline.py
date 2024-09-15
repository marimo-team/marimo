# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.8.3"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo

    return (mo,)


@app.cell
def __(mo):
    mo.md("# Heading 1")
    return


@app.cell
def __(mo):
    mo.carousel([mo.md("# Carousel Heading")])
    return


@app.cell
def __(mo):
    mo.md("# Heading 2 \n\n Headings between carousel and tabs are detected")
    return


@app.cell
def __(mo):
    mo.ui.tabs({"Tab 1": mo.md("# Tabs Heading")})
    return


@app.cell
def __(mo):
    mo.md("# Heading 3 \n\n Headings between tabs and accordion are detected")
    return


@app.cell
def __(mo):
    mo.accordion({"Accordion 1": mo.md("# Accordion Heading")})
    return


@app.cell
def __(mo):
    mo.md("# Heading 4")
    return


if __name__ == "__main__":
    app.run()

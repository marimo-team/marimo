# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.2.1"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.md("# Tables")
    return


@app.cell
def __(mo):
    mo.md(
        """
        First Header  | Second Header
        ------------- | -------------
        Content Cell  | Content Cell
        $f(x)$        | Content Cell
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        """
        | Tables        | Are           | Cool  |
        | ------------- |:-------------:| -----:|
        | col 3 is      | right-aligned | $1600 |
        | col 2 is      | centered      |   $12 |
        | zebra stripes | are neat      |    $1 |
        """
    )
    return


@app.cell
def __(mo):
    mo.md("# Footnotes")
    return


@app.cell
def __(mo):
    mo.md(
        """
        Here's a short footnote,[^1] and here's a longer one.[^longnote]

        [^1]: This is a short footnote.

        [^longnote]: This is a longer footnote with paragraphs, and code.

            Indent paragraphs to include them in the footnote.

            `{ my code }` add some code, if you like.

            Add as many paragraphs as you need.
        """
    )
    return


@app.cell
def __(mo):
    mo.md("# External links")
    return


@app.cell
def __(mo):
    mo.md(
        """
        This is [an example](http://example.com/ "Title") inline link.

        [This link](http://example.net/) has no title attribute.
        """
    )
    return


if __name__ == "__main__":
    app.run()

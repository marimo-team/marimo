# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "altair",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import altair as alt

    alt.themes
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()

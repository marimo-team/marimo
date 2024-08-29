# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "altair",
# ]
# ///

import marimo

__generated_with = "0.8.3"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    import altair as alt

    alt.themes
    return alt, mo


@app.cell
def __():
    return


if __name__ == "__main__":
    app.run()

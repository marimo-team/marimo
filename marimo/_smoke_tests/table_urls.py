# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.20"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    mo.ui.table(
      [
        { "title": 'New York', "url": 'https://en.wikipedia.org/wiki/New_York_City', },
        { "title": 'London', "url": 'https://en.wikipedia.org/wiki/London', },
        { "title": 'Paris', "url": 'https://en.wikipedia.org/wiki/Paris', },
      ],
    )
    return


if __name__ == "__main__":
    app.run()

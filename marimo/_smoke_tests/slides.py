# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "altair",
#     "pandas",
#     "marimo",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.8.11"
app = marimo.App(layout_file="layouts/slides.slides.json")


@app.cell
def __(mo):
    mo.md("""# A Presentation on `Iris` Data""")
    return


@app.cell
def __(mo):
    mo.md("""## By the marimo team (`@marimo_io`)""")
    return


@app.cell
def __():
    import marimo as mo
    import pandas as pd
    import altair as alt
    return alt, mo, pd


@app.cell
def __(pd):
    df = pd.read_csv(
        "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv"
    )
    return df,


@app.cell
def __(df, mo):
    table = mo.ui.table(df, label="Iris Data in a table")
    table
    return table,


@app.cell
def __(alt, df, mo):
    chart = mo.ui.altair_chart(
        alt.Chart(df)
        .mark_point()
        .encode(x="sepal_length", y="sepal_width", color="species"),
        label="Iris Data in chart",
    )
    chart
    return chart,


@app.cell
def __(mo):
    mo.md("""# Thank you!""")
    return


@app.cell
def __():
    # Some markdown testing
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        # H1 (`H1`)
        ## H2 (`H2`)
        ### H3 (`H3`)
        #### H4 (`H4`)
        ##### H5 (`H5`)
        ###### H6 (`H6`)
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        - Item 1
        - `Item 2`
        - **Item 3**
        - _Item 4_
        """
    )
    return


@app.cell
def __(mo):
    mo.md(
        r"""
        !!! note "Callouts"
            This is a callout
        """
    )
    return


@app.cell
def __(mo):
    mo.callout("""
    This is another callout
    """)
    return


@app.cell
def __():
    return


@app.cell
def __(mo):
    mo.md(r"""## Items that don't quite work in slides""")
    return


@app.cell
def __(mo):
    mo.accordion({"Accodrions too small": mo.md("Content")})
    return


@app.cell
def __(mo):
    mo.ui.tabs({"Tabs to small": mo.md("Content")})
    return


if __name__ == "__main__":
    app.run()

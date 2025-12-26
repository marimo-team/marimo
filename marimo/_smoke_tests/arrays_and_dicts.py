# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    items = mo.ui.array(
        [
            mo.ui.text("name", "Name"),
            mo.ui.text("age", "Age"),
            mo.ui.text("email", "Email"),
            mo.ui.text("phone", "Phone"),
            mo.ui.text("address", "Address"),
            mo.ui.text("memo", "Memo"),
        ]
    )
    return (items,)


@app.cell
def _(items):
    items
    return


@app.cell
def _(items):
    items.hstack(gap=2)
    return


@app.cell
def _(mo):
    dictionary = mo.ui.dictionary(
        {
            "name": mo.ui.text("name", "Name"),
            "age": mo.ui.text("age", "Age"),
            "email": mo.ui.text("email", "Email"),
            "phone": mo.ui.text("phone", "Phone"),
            "address": mo.ui.text("address", "Address"),
            "memo": mo.ui.text("memo", "Memo"),
        }
    )
    return (dictionary,)


@app.cell
def _(dictionary):
    dictionary
    return


@app.cell
def _(dictionary):
    dictionary.vstack()
    return


if __name__ == "__main__":
    app.run()

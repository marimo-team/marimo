# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.2.3"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
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
    return items,


@app.cell
def __(items):
    items
    return


@app.cell
def __(items):
    items.hstack(gap=2)
    return


@app.cell
def __(mo):
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
    return dictionary,


@app.cell
def __(dictionary):
    dictionary
    return


@app.cell
def __(dictionary):
    dictionary.vstack()
    return


if __name__ == "__main__":
    app.run()

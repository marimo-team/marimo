# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.6"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    dict1={"hello": mo.ui.text(label="world")}
    dict2=mo.ui.dictionary({k: v.form() for k, v in dict1.items()})
    dict2
    return dict1, dict2


@app.cell
def __(dict2):
    dict2.value
    return


if __name__ == "__main__":
    app.run()

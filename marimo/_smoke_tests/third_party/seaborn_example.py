# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "seaborn",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell(hide_code=True)
def _():
    import seaborn as sns

    penguins = sns.load_dataset("penguins")
    tips = sns.load_dataset("tips")
    return penguins, sns, tips


@app.cell
def _(sns):
    sns.color_palette("pastel")
    return


@app.cell
def _(penguins, sns):
    sns.jointplot(
        data=penguins,
        x="flipper_length_mm",
        y="bill_length_mm",
        hue="species",
    )
    return


@app.cell
def _(penguins, sns):
    sns.pairplot(data=penguins, hue="species")
    return


@app.cell
def _(sns, tips):
    sns.relplot(
        data=tips,
        x="total_bill",
        y="tip",
        col="time",
        hue="smoker",
        style="smoker",
        size="size",
    )
    return


if __name__ == "__main__":
    app.run()

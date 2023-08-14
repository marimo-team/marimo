# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __():
    import seaborn as sns

    penguins = sns.load_dataset("penguins")
    tips = sns.load_dataset("tips")
    return penguins, sns, tips


@app.cell
def __(penguins, sns):
    sns.jointplot(
        data=penguins,
        x="flipper_length_mm",
        y="bill_length_mm",
        hue="species",
    )
    return


@app.cell
def __(penguins, sns):
    sns.pairplot(data=penguins, hue="species")
    return


@app.cell
def __(sns, tips):
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

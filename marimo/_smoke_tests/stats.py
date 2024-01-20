# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.29"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    _stats = [
        mo.stat("$100", label="Revenue", caption="+ 10%", direction="increase"),
        mo.stat(
            "$20", label="Marketing spend", caption="+ 10%", direction="increase"
        ),
        mo.stat("$80", label="Profit", caption="+ 10%", direction="increase"),
        mo.stat("2%", label="Churn", caption="- 2%", direction="decrease"),
    ]
    mo.hstack(_stats)
    return


@app.cell
def __(mo):
    _stats = [
        mo.stat(
            "$100",
            label="Revenue",
            caption="+ 10%",
            direction="increase",
            bordered=True,
        ),
        mo.stat(
            "$20",
            label="Marketing spend",
            caption="+ 10%",
            direction="increase",
            bordered=True,
        ),
        mo.stat(
            "$80",
            label="Profit",
            caption="+ 10%",
            direction="increase",
            bordered=True,
        ),
        mo.stat(
            "2%",
            label="Churn",
            caption="- 2%",
            direction="decrease",
            bordered=True,
        ),
    ]
    mo.hstack(_stats, widths="equal", gap=1)
    return


if __name__ == "__main__":
    app.run()

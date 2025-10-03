import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd

    import marimo as mo
    return mo, pd


@app.cell
def _():
    data = [
        {
            "block_number": 8021365,
            "blockNumber": 2216021,
            "txnHash": "0x991923a4d6979630dd6be2f81e8adda2cb5ed1c7be8912c6c8636c48be40b990",
        }
    ]
    return (data,)


@app.cell
def _(data, mo, pd):
    mo.ui.table(pd.DataFrame(data))
    return


@app.cell
def _(data, mo, pd):
    mo.ui.dataframe(pd.DataFrame(data))
    return


if __name__ == "__main__":
    app.run()

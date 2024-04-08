# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.3.9"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Visualization: Time Series Line Plot in Altair

        Altair handles temporal types natively by using the ``:T`` type marker. An example is in this plot of stock prices over time
        """
    )
    return


@app.cell
def __():
    from vega_datasets import data

    stocks = data.stocks()

    import altair as alt

    alt.Chart(stocks).mark_line().encode(
        x="date:T", y="price", color="symbol"
    ).interactive(bind_y=False)
    return alt, data, stocks


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()

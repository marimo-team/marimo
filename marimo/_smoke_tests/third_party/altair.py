# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(data):
    cars = data.cars()
    stocks = data.stocks.url
    source = data.windvectors()
    return cars, source, stocks


@app.cell
def __(alt, source):
    alt.Chart(source).mark_point(shape="wedge", filled=True).encode(
        latitude="latitude",
        longitude="longitude",
        color=alt.Color(
            "dir",
            scale=alt.Scale(domain=[0, 360], scheme="rainbow"),
            legend=None,
        ),
        angle=alt.Angle(
            "dir", scale=alt.Scale(domain=[0, 360], range=[180, 540])
        ),
        size=alt.Size("speed", scale=alt.Scale(rangeMax=500)),
    ).project("equalEarth")
    return


@app.cell
def __(alt, cars, mo):
    cars_scatter_plot = (
        alt.Chart(cars)
        .mark_circle(size=60)
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
            tooltip=["Name", "Origin", "Horsepower", "Miles_per_Gallon"],
        )
        .interactive()
    )

    mo.md(
        f"""# hello, world

        {mo.as_html(cars_scatter_plot)}

        that was an altair plot
        """
    )
    return cars_scatter_plot,


@app.cell
def __(alt, datum, stocks):
    base = (
        alt.Chart(stocks)
        .encode(x="date:T", y="price:Q", color="symbol:N")
        .transform_filter(datum.symbol == "GOOG")
    )

    (base.mark_line() + base.mark_point())
    return base,


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __():
    import altair as alt
    from altair.expr import datum
    from vega_datasets import data
    return alt, data, datum


if __name__ == "__main__":
    app.run()

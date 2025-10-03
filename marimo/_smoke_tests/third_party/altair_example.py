# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "vega-datasets",
#     "altair",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _(data):
    cars = data.cars()
    stocks = data.stocks.url
    source = data.windvectors()
    return cars, source, stocks


@app.cell
def _(alt, source):
    alt.Chart(source).mark_point(shape="wedge", filled=True).encode(
        latitude="latitude",
        longitude="longitude",
        color=alt.Color(
            "dir",
            scale=alt.Scale(domain=[0, 360], scheme="rainbow"),
            legend=None,
        ),
        angle=alt.Angle("dir", scale=alt.Scale(domain=[0, 360], range=[180, 540])),
        size=alt.Size("speed", scale=alt.Scale(rangeMax=500)),
    ).project("equalEarth")
    return


@app.cell
def _(alt, cars, mo):
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
    return


@app.cell
def _(alt, stocks):
    base = (
        alt.Chart(stocks)
        .encode(x="date:T", y="price:Q", color="symbol:N")
        .transform_filter(alt.datum.symbol == "GOOG")
    )

    (base.mark_line() + base.mark_point())
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import altair as alt
    from vega_datasets import data
    return alt, data


if __name__ == "__main__":
    app.run()

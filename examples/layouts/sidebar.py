# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "altair==5.4.1",
#     "marimo",
#     "vega-datasets==0.9.0",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    !!! tip "This notebook is best viewed as an app."
        Hit `Cmd/Ctrl+.` or click the "app view" button in the bottom right.
    """)
    return


@app.cell
def _():
    import marimo as mo
    import altair as alt
    from vega_datasets import data

    return alt, data, mo


@app.cell
def _(data):
    gapminder = data.gapminder()
    return (gapminder,)


@app.cell
def _(gapminder, mo):
    # Filters
    year = mo.ui.slider.from_series(
        gapminder["year"], full_width=True, label="Year", step=5
    )
    population = mo.ui.range_slider.from_series(
        gapminder["pop"], full_width=True, label="Population"
    )
    return population, year


@app.cell
def _(gapminder, population, year):
    # Filter the dataset
    filtered_data = gapminder[
        (gapminder["year"] == year.value)
        & (gapminder["pop"] > population.value[0])
        & (gapminder["pop"] < population.value[1])
    ]
    return (filtered_data,)


@app.cell
def _(alt, filtered_data, mo):
    chart = mo.ui.altair_chart(
        alt.Chart(filtered_data)
        .mark_circle(opacity=0.7)
        .encode(
            x="fertility:Q",
            y="life_expect:Q",
            color="cluster:N",
            size=alt.Size("pop:Q", scale=alt.Scale(range=[100, 2000])),
            tooltip=[
                "country:N",
                "year:O",
                "fertility:Q",
                "life_expect:Q",
                "pop:Q",
            ],
        )
        .properties(height=400)
    )
    chart
    return (chart,)


@app.cell
def _(chart):
    # Show the chart selection
    chart.value if not chart.value.empty else None
    return


@app.cell
def _(mo, population, year):
    mo.sidebar(
        [
            mo.md("# Gap Minder"),
            mo.md(
                "Scrub the year to see life expectancy go up and fertility go down"
            ),
            mo.vstack(
                [
                    year,
                    mo.md(f"{int(year.value)}"),
                    population,
                    mo.md(
                        f"{int(population.value[0]):,} - {int(population.value[1]):,}"
                    ),
                ]
            ).style(padding="20px 10px"),
        ],
        footer=[
            mo.md(
                f"""
            [{mo.icon("lucide:twitter")} Twitter](https://twitter.com/marimo_io)

            [{mo.icon("lucide:github")} GitHub](https://github.com/marimo-team/marimo)    
            """
            )
        ],
    )
    return


if __name__ == "__main__":
    app.run()

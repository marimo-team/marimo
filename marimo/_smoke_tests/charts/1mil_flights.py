# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "vega-datasets",
#     "altair",
#     "pandas",
#     "marimo",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="full")


@app.cell
def _(pd):
    # Load some large data
    all_flights = pd.read_parquet(
        "https://vegafusion-datasets.s3.amazonaws.com/vega/flights_1m.parquet"
    )
    return (all_flights,)


@app.cell
def _(mo):
    size = mo.ui.dropdown(
        label="Size",
        options=["100", "1000", "10000", "100000", "1000000"],
        value="100000",
    )
    size
    return (size,)


@app.cell
def _(alt, flights, mo):
    scatter = mo.ui.altair_chart(
        alt.Chart(flights).mark_point().encode(x="delay:Q", y="distance:Q")
    )
    scatter
    return (scatter,)


@app.cell
def _(scatter):
    scatter.value.head()
    return


@app.cell
def _(all_flights, size):
    flights = all_flights.sample(int(size.value))
    return (flights,)


@app.cell
def _(flights):
    f"{len(flights):,} flights"
    return


@app.cell
def _(alt, mo, pd):
    # List available data transformers
    mo.ui.altair_chart(alt.Chart(pd.DataFrame({"a": [1]})).mark_point())
    mo.accordion(
        {
            "Debug": mo.md(
                f"""
    Available data transformers: **{", ".join(alt.data_transformers.names())}**

    Current data transformer: **{alt.data_transformers.active}**
    """
            )
        }
    )
    return


@app.cell
def _(alt, flights, mo):
    flight_histogram = mo.ui.altair_chart(
        alt.Chart(flights).mark_bar().encode(alt.X("delay"), alt.Y("count()"))
    )
    flight_histogram
    return (flight_histogram,)


@app.cell
def _(flight_histogram, mo):
    mo.stop(len(flight_histogram.value) == 0, None)

    mo.md(f"Selected **{len(flight_histogram.value):,}** flights")
    return


@app.cell
def _(alt, flight_histogram, mo):
    mo.stop(len(flight_histogram.value) == 0, None)

    origin_chart = mo.ui.altair_chart(
        alt.Chart(flight_histogram.value)
        .mark_bar()
        .encode(alt.X("origin:O"), alt.Y("count()"))
    )
    destination_chart = mo.ui.altair_chart(
        alt.Chart(flight_histogram.value)
        .mark_bar()
        .encode(alt.X("destination:O"), alt.Y("count()"))
    )
    mo.hstack([origin_chart, destination_chart])
    return


@app.cell
def _(airports, alt, data, flight_histogram, mo):
    flights_airport = flight_histogram.value
    # flights_airport = data.flights_airport.url

    states = alt.topo_feature(data.us_10m.url, feature="states")

    # Create mouseover selection
    select_city = alt.selection_point(
        on="mouseover", nearest=True, fields=["origin"], empty=False
    )

    # Define which attributes to lookup from airports.csv
    lookup_data = alt.LookupData(
        airports, key="iata", fields=["state", "latitude", "longitude"]
    )

    background = (
        alt.Chart(states)
        .mark_geoshape(fill="lightgray", stroke="white")
        .properties(width=750, height=500)
        .project("albersUsa")
    )

    connections = (
        alt.Chart(flights_airport)
        .mark_rule(opacity=0.5, strokeWidth=0.04)
        .encode(
            latitude="latitude:Q",
            longitude="longitude:Q",
            latitude2="lat2:Q",
            longitude2="lon2:Q",
        )
        .transform_lookup(lookup="origin", from_=lookup_data)
        .transform_lookup(
            lookup="destination",
            from_=lookup_data,
            as_=["state", "lat2", "lon2"],
        )
        .transform_filter(select_city)
    )

    points = (
        alt.Chart(flights_airport)
        .mark_circle()
        .encode(
            latitude="latitude:Q",
            longitude="longitude:Q",
            size=alt.Size("routes:Q").legend(None).scale(range=[0, 1000]),
            order=alt.Order("routes:Q").sort("descending"),
            tooltip=["origin:N", "routes:Q"],
        )
        .transform_aggregate(routes="count()", groupby=["origin"])
        .transform_lookup(lookup="origin", from_=lookup_data)
        .transform_filter(
            (alt.datum.state != "PR") & (alt.datum.state != "VI")
        )
        .add_params(select_city)
    )

    mo.ui.altair_chart(
        (background + connections + points).configure_view(stroke=None)
    )
    return


@app.cell
def _(flight_histogram, mo):
    mo.stop(len(flight_histogram.value) == 0, None)

    mo.hstack(
        [
            mo.md(
                f"Top airport: **{flight_histogram.value['origin'].value_counts().index[0]}**"
            ),
            flight_histogram.value.describe(),
            mo.ui.table(flight_histogram.value),
        ]
    )
    return


@app.cell(disabled=True)
def _(alt, brush, flights, mo):
    # Run the same chart with vegafusion
    with alt.data_transformers.enable("vegafusion"):
        million_histogram = (
            alt.Chart(flights)
            .mark_bar()
            .encode(alt.X("delay"), alt.Y("count()"))
            .add_params(brush)
        )
        mo.output.append(mo.ui.altair_chart(million_histogram))
    return


@app.cell
def _():
    import altair as alt
    import pandas as pd
    from vega_datasets import data

    import marimo as mo

    airports = data.airports.url

    None
    return airports, alt, data, mo, pd


if __name__ == "__main__":
    app.run()

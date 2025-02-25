import marimo

__generated_with = "0.11.8"
app = marimo.App(width="columns")


@app.cell(column=0, hide_code=True)
def _(mo):
    mo.md(r"""# Selections with altair maps""")
    return


@app.cell(hide_code=True)
def _():
    import altair as alt
    from vega_datasets import data
    import geopandas as gpd
    return alt, data, gpd


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## Load the data""")
    return


@app.cell(hide_code=True)
def _(data, gpd):
    # load the data
    us_states = gpd.read_file(data.us_10m.url, driver="TopoJSON", layer="states")
    us_population = data.population_engineers_hurricanes()[
        ["state", "id", "population"]
    ]

    gdf_quakies = gpd.read_file(data.earthquakes.url, driver="GeoJSON")
    gdf_world = gpd.read_file(data.world_110m.url, driver="TopoJSON")
    return gdf_quakies, gdf_world, us_population, us_states


@app.cell(column=1, hide_code=True)
def _(mo):
    mo.md(
        r"""
        ## Example 1: Population map

        https://altair-viz.github.io/user_guide/marks/geoshape.html#interactions
        """
    )
    return


@app.cell(hide_code=True)
def _(alt, us_population, us_states):
    def population_map():
        # define a pointer selection
        click_state = alt.selection_point(fields=["state"])
        # define a condition on the opacity encoding depending on the selection
        opacity = alt.when(click_state).then(alt.value(1)).otherwise(alt.value(0.2))

        # create a choropleth map using a lookup transform
        choropleth = (
            alt.Chart(us_states)
            .mark_geoshape()
            .transform_lookup(
                lookup="id",
                from_=alt.LookupData(us_population, "id", ["population", "state"]),
            )
            .encode(
                color="population:Q",
                opacity=opacity,
                tooltip=["state:N", "population:Q"],
            )
            .project(type="albersUsa")
        )

        # create a bar chart with the same conditional ``opacity`` encoding.
        bars = (
            alt.Chart(
                us_population.nlargest(15, "population"),
                title="Top 15 states by population",
            )
            .mark_bar()
            .encode(
                x="population",
                opacity=opacity,
                color="population",
                y=alt.Y("state").sort("-x"),
            )
        )

        return (choropleth & bars).add_params(click_state)
    return (population_map,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""### Without `mo.ui.altair_chart`""")
    return


@app.cell
def _(population_map):
    population_map()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### With `mo.ui.altair_chart`""")
    return


@app.cell
def _(mo, population_map):
    chart = mo.ui.altair_chart(population_map())
    chart
    return (chart,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""Selecting the bar chart or map should filter the table below""")
    return


@app.cell
def _(chart, mo, us_population):
    mo.hstack([chart.selections, chart.apply_selection(us_population)])
    return


@app.cell
def _():
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    return


@app.cell(column=2)
def _(mo):
    mo.md("""## Example 2:""")
    return


@app.cell(hide_code=True)
def _(alt, gdf_quakies, gdf_world):
    def world_map():
        # define parameters
        range0 = alt.binding_range(
            min=-180, max=180, step=5, name="rotate longitude "
        )
        rotate0 = alt.param(value=120, bind=range0)
        hover = alt.selection_point(on="pointerover", clear="pointerout")

        # world disk
        sphere = alt.Chart(alt.sphere()).mark_geoshape(
            fill="aliceblue", stroke="black", strokeWidth=1.5
        )

        # countries as shapes
        world = alt.Chart(gdf_world).mark_geoshape(
            fill="mintcream", stroke="black", strokeWidth=0.35
        )

        # earthquakes as circles with fill for depth and size for magnitude
        # the hover param is added on the mar_circle only
        quakes = (
            alt.Chart(gdf_quakies)
            .mark_circle(opacity=0.35, tooltip=True, stroke="black")
            .transform_calculate(
                lon="datum.geometry.coordinates[0]",
                lat="datum.geometry.coordinates[1]",
                depth="datum.geometry.coordinates[2]",
            )
            .transform_filter(
                (
                    (rotate0 * -1 - 90 < alt.datum.lon)
                    & (alt.datum.lon < rotate0 * -1 + 90)
                ).expr
            )
            .encode(
                longitude="lon:Q",
                latitude="lat:Q",
                strokeWidth=alt.when(hover, empty=False)
                .then(alt.value(1))
                .otherwise(alt.value(0)),
                size=alt.Size(
                    "mag:Q",
                    scale=alt.Scale(
                        type="pow", range=[1, 1000], domain=[0, 6], exponent=4
                    ),
                ),
                fill=alt.Fill(
                    "depth:Q",
                    scale=alt.Scale(scheme="lightorange", domain=[0, 400]),
                ),
            )
            .add_params(hover, rotate0)
        )

        # define projection and add the rotation param for all layers
        comb = alt.layer(sphere, world, quakes).project(
            type="orthographic", rotate=alt.expr(f"[{rotate0.name}, 0, 0]")
        )
        return comb
    return (world_map,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""### Without `mo.ui.altair_chart`""")
    return


@app.cell
def _(world_map):
    world_map()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""### With `mo.ui.altair_chart`""")
    return


@app.cell
def _(mo, world_map):
    world = mo.ui.altair_chart(world_map())
    world
    return (world,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""Hovering over an element on the map should filter the table below.""")
    return


@app.cell
def _(world):
    str(world.selections)
    return


@app.cell
def _(gdf_quakies, gdf_world, mo, world):
    mo.hstack(
        [
            world.apply_selection(gdf_quakies)["title"],
            world.apply_selection(gdf_world)["id"],
        ]
    )
    return


if __name__ == "__main__":
    app.run()

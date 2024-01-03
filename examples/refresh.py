import marimo

__generated_with = "0.1.68"
app = marimo.App(width="full")


@app.cell
def __(
    chart,
    iss_df,
    mo,
    n_points_slider,
    refresh_interval_slider,
    refresher,
):
    mo.hstack([
        mo.vstack([
            mo.md("## Settings | [`marimo.ui.slider`](https://docs.marimo.io/api/inputs/slider.html), [`marimo.ui.refresh`](https://docs.marimo.io/recipes.html#run-a-cell-on-a-timer)\n---"),
            refresh_interval_slider,
            n_points_slider,
            refresher,
            mo.md("## ISS Positions | [`marimo.ui.altair_chart`](https://docs.marimo.io/api/plotting.html#marimo.ui.altair_chart)\n---"),
            mo.as_html(chart).style({"width": "700px"})
        ], align="center"),
        mo.vstack([
            mo.md("## Data | [`marimo.as_html`](https://docs.marimo.io/api/html.html)`(pd.DataFrame)`\n---"),
            mo.as_html(iss_df)
        ])
    ], justify="center", wrap=True, gap=3)
    return


@app.cell
def __(alt, get_iss_positions, sphere, world):
    hover=alt.selection_point(on="mouseover", clear="mouseout")

    # iss positions
    iss_df = get_iss_positions()
    iss = alt.Chart(iss_df[['longitude','latitude','timestamp']]).mark_circle(
        stroke='black', size=100,
    ).encode(
        longitude=alt.Longitude('longitude:Q'),
        latitude='latitude:Q',
        fill=alt.Fill('timestamp:Q', scale=alt.Scale(scheme='purples'), legend=None),
        strokeWidth=alt.condition(hover, alt.value(3, empty=False), alt.value(0)),
        tooltip=[
            alt.Tooltip('longitude:Q', title='Longitude', format='.4f'),
            alt.Tooltip('latitude:Q', title='Latitude', format='.4f'),
            alt.Tooltip('timestamp:T', title='Timestamp', format='%Y-%m-%d %H:%M:%S')
        ]
    ).add_params(hover)

    chart = alt.layer(sphere, world, iss).project(type="naturalEarth1").properties(width=640, title="")
    return chart, hover, iss, iss_df


@app.cell
def __(alt, data):
    # load geo data from Vega Datasets
    countries = alt.topo_feature(data.world_110m.url, 'countries')

    # world base
    sphere = alt.Chart(alt.sphere()).mark_geoshape(
        fill="aliceblue", stroke="black", strokeWidth=1.5
    )

    # world map
    world = alt.Chart(countries).mark_geoshape(
        fill="mintcream", stroke="black", strokeWidth=0.35
    )
    return countries, sphere, world


@app.cell
def __(
    n_points_slider,
    pd,
    refresh_interval_slider,
    refresher,
    requests,
    time,
):
    def get_iss_positions(refresher=refresher):
        refresher
        timepoints = [int(time())]
        while len(timepoints) <= n_points_slider.value:
            timepoints.append(timepoints[-1] - refresh_interval_slider.value)
        else:
            timepoints.pop(0)
        timepoints_str = str(timepoints)[1:-1].replace(" ", "")
        iss_url = f"https://api.wheretheiss.at/v1/satellites/25544/positions?timestamps={timepoints_str}"
        response = requests.get(iss_url)
        df = pd.DataFrame(response.json())
        df['timestamp'] = pd.to_datetime(df.timestamp, unit='s')
        return df[['timestamp','latitude','longitude','altitude','velocity','visibility']]
    return get_iss_positions,


@app.cell
def __(mo, refresh_interval_slider):
    refresher = mo.ui.refresh(default_interval=f"{refresh_interval_slider.value}s")
    return refresher,


@app.cell
def __(mo):
    refresh_interval_slider = mo.ui.slider(start=5, stop=60, step=1, value=10, label="refresh interval (default = 10 sec)")
    n_points_slider = mo.ui.slider(start=5, stop=30, step=1, value=15, label="number of points (default = 15)")
    return n_points_slider, refresh_interval_slider


@app.cell
def __():
    import altair as alt
    import marimo as mo
    import pandas as pd
    import requests
    from time import time
    from vega_datasets import data

    pd.options.display.max_rows = 30
    return alt, data, mo, pd, requests, time


if __name__ == "__main__":
    app.run()

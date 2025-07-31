# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "geopandas==1.0.1",
#     "lonboard==0.10.4",
#     "marimo",
#     "matplotlib==3.10.3",
#     "palettable==3.3.3",
#     "pandas==2.2.3",
#     "pyarrow==20.0.0",
#     "shapely==2.1.1",
# ]
# ///

import marimo

__generated_with = "0.13.10"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    from pathlib import Path

    import geopandas as gpd
    import pandas as pd
    import shapely
    from palettable.colorbrewer.diverging import BrBG_10

    from lonboard import Map, ScatterplotLayer
    from lonboard.colormap import apply_continuous_cmap
    return (
        BrBG_10,
        Map,
        Path,
        ScatterplotLayer,
        apply_continuous_cmap,
        gpd,
        mo,
        pd,
        shapely,
    )


@app.cell
def _(Path, gpd, pd, shapely):
    _url = "https://ookla-open-data.s3.us-west-2.amazonaws.com/parquet/performance/type=mobile/year=2019/quarter=1/2019-01-01_performance_mobile_tiles.parquet"

    _local_path = Path("internet-speeds.parquet")
    if _local_path.exists():
        gdf = gpd.read_parquet(_local_path)
    else:
        _columns = ["avg_d_kbps", "tile"]
        _df = pd.read_parquet(_url, columns=_columns)

        _tile_geometries = shapely.from_wkt(_df["tile"])
        _tile_centroids = shapely.centroid(_tile_geometries)
        gdf = gpd.GeoDataFrame(
            _df[["avg_d_kbps"]], geometry=_tile_centroids, crs="EPSG:4326"
        )
        gdf.to_parquet(_local_path)

    gdf
    return (gdf,)


@app.cell
def _(Map, ScatterplotLayer, gdf, mo):
    layer = ScatterplotLayer.from_geopandas(gdf)
    min_bound = mo.ui.slider(
        0, 100_000, value=5000, show_value=True, label="min bound"
    )
    max_bound = mo.ui.slider(
        0, 100_000, value=50_000, show_value=True, label="max bound"
    )
    mo.vstack([min_bound, max_bound, Map(layer, _height=600)])
    return layer, max_bound, min_bound


@app.cell
def _(BrBG_10, apply_continuous_cmap, gdf, layer, max_bound, min_bound):
    normalized_download_speed = (gdf["avg_d_kbps"] - min_bound.value) / (
        max_bound.value - min_bound.value
    )
    layer.get_fill_color = apply_continuous_cmap(
        normalized_download_speed, BrBG_10, alpha=0.7
    )
    return


@app.cell
def _(layer):
    layer.get_fill_color[0]
    return


if __name__ == "__main__":
    app.run()

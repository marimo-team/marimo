# Copyright 2026 Marimo. All rights reserved.
"""Geometry fixture corpus for table-manager characterization tests.

One factory function per fixture. Geo sources cover GeoPandas, GeoArrow
(WKB and WKT), DuckDB spatial, and ibis. False-positive fixtures look
like geometry but must never be detected as geometry. Ordinary data
feeds the ordinary-table payload baselines.

Callers gate on `pytest.mark.requires(...)`; functions assume their
libraries are installed except the duckdb spatial helpers, which skip
when the extension cannot load.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    import duckdb as duckdb_mod
    import geopandas as gpd_mod
    import ibis as ibis_mod
    import pyarrow as pa_mod

# WKB for POINT (1 2), little-endian.
WKB_POINT_1_2 = bytes.fromhex("0101000000000000000000f03f0000000000000040")

# Two valid H3 cell ids (resolution 10), stored as plain uint64 ints.
H3_CELLS = [0x8A2A1072B59FFFF, 0x8A2A1072B597FFF]


# --- GeoPandas ---------------------------------------------------------


def gdf_point_known_crs() -> gpd_mod.GeoDataFrame:
    import geopandas as gpd
    from shapely.geometry import Point

    return gpd.GeoDataFrame(
        {"name": ["a", "b"]},
        geometry=[Point(0, 0), Point(1, 1)],
        crs="EPSG:4326",
    )


def gdf_point_missing_crs() -> gpd_mod.GeoDataFrame:
    import geopandas as gpd
    from shapely.geometry import Point

    return gpd.GeoDataFrame(
        {"name": ["a", "b"]},
        geometry=[Point(0, 0), Point(1, 1)],
    )


def gdf_multi_geometry() -> gpd_mod.GeoDataFrame:
    """Two geometry columns with independent CRS; `geom_a` is active."""
    import geopandas as gpd
    from shapely.geometry import Point

    return gpd.GeoDataFrame(
        {
            "geom_a": gpd.GeoSeries(
                [Point(0, 0), Point(1, 1)], crs="EPSG:4326"
            ),
            "geom_b": gpd.GeoSeries(
                [Point(2, 2), Point(3, 3)], crs="EPSG:3857"
            ),
        },
        geometry="geom_a",
    )


def gdf_no_active_geometry() -> gpd_mod.GeoDataFrame:
    """A geometry column exists but no active geometry is set."""
    import geopandas as gpd
    from shapely.geometry import Point

    return gpd.GeoDataFrame(
        {
            "a": [1, 2],
            "g": gpd.GeoSeries([Point(0, 0), Point(1, 1)]),
        }
    )


def gdf_stale_pointer() -> gpd_mod.GeoDataFrame:
    """The active-geometry pointer names a column that was renamed away."""
    return gdf_point_known_crs().rename(columns={"geometry": "geom"})


def gdf_dropped_active() -> Any:
    """The active geometry column was dropped; another geometry remains."""
    return gdf_multi_geometry().drop(columns=["geom_a"])


def gdf_with_null() -> gpd_mod.GeoDataFrame:
    import geopandas as gpd
    from shapely.geometry import Point

    return gpd.GeoDataFrame(
        {"name": ["a", "b"]},
        geometry=[Point(0, 0), None],
        crs="EPSG:4326",
    )


def gdf_all_null() -> gpd_mod.GeoDataFrame:
    import geopandas as gpd

    return gpd.GeoDataFrame(
        {"name": ["a", "b"]},
        geometry=gpd.GeoSeries([None, None]),
    )


def gdf_mixed_types() -> gpd_mod.GeoDataFrame:
    import geopandas as gpd
    from shapely.geometry import LineString, Point, Polygon

    return gpd.GeoDataFrame(
        {"name": ["pt", "line", "poly"]},
        geometry=[
            Point(0, 0),
            LineString([(0, 0), (1, 1)]),
            Polygon([(0, 0), (1, 0), (1, 1)]),
        ],
        crs="EPSG:4326",
    )


def gdf_3d() -> gpd_mod.GeoDataFrame:
    import geopandas as gpd
    from shapely.geometry import Point

    return gpd.GeoDataFrame(
        {"name": ["a"]},
        geometry=[Point(1, 2, 3)],
        crs="EPSG:4326",
    )


# --- GeoArrow (hand-built metadata; no geoarrow library) ---------------


def _arrow_table_with_extension(
    extension_name: str,
    values: list[Any],
    value_type: pa_mod.DataType,
    *,
    crs: bool,
) -> pa_mod.Table:
    import pyarrow as pa

    metadata: dict[bytes, bytes] = {
        b"ARROW:extension:name": extension_name.encode(),
    }
    if crs:
        metadata[b"ARROW:extension:metadata"] = b'{"crs": "EPSG:4326"}'
    schema = pa.schema(
        [
            pa.field("a", pa.int64()),
            pa.field("geom", value_type, metadata=metadata),
        ]
    )
    return pa.table(
        {"a": list(range(len(values))), "geom": values}, schema=schema
    )


def arrow_wkb_known_crs() -> pa_mod.Table:
    import pyarrow as pa

    return _arrow_table_with_extension(
        "geoarrow.wkb", [WKB_POINT_1_2, None], pa.binary(), crs=True
    )


def arrow_wkb_missing_crs() -> pa_mod.Table:
    import pyarrow as pa

    return _arrow_table_with_extension(
        "geoarrow.wkb", [WKB_POINT_1_2, WKB_POINT_1_2], pa.binary(), crs=False
    )


def arrow_ogc_wkb() -> pa_mod.Table:
    import pyarrow as pa

    return _arrow_table_with_extension(
        "ogc.wkb", [WKB_POINT_1_2], pa.binary(), crs=False
    )


def arrow_wkt() -> pa_mod.Table:
    import pyarrow as pa

    return _arrow_table_with_extension(
        "geoarrow.wkt",
        ["POINT (1 2)", "POINT Z (1 2 3)", None],
        pa.string(),
        crs=True,
    )


def arrow_other_geoarrow() -> pa_mod.Table:
    """A geoarrow extension that is neither wkb nor wkt."""
    import pyarrow as pa

    return _arrow_table_with_extension(
        "geoarrow.point",
        [None, None],
        pa.list_(pa.float64(), 2),
        crs=False,
    )


# --- DuckDB spatial ----------------------------------------------------


def duckdb_spatial_connection() -> duckdb_mod.DuckDBPyConnection:
    """In-memory connection with the spatial extension, or skip.

    `INSTALL spatial` downloads the extension, so network-blocked
    runners skip these fixtures instead of failing.
    """
    import duckdb

    conn = duckdb.connect()
    try:
        conn.execute("INSTALL spatial")
        conn.execute("LOAD spatial")
    except duckdb.Error as e:
        conn.close()
        pytest.skip(f"duckdb spatial extension unavailable: {e}")
    return conn


def duckdb_geometry_relation(
    conn: duckdb_mod.DuckDBPyConnection,
) -> duckdb_mod.DuckDBPyRelation:
    return conn.sql(
        "SELECT 1 AS a, ST_Point(1.0, 2.0) AS geom UNION ALL SELECT 2, NULL"
    )


# --- ibis --------------------------------------------------------------


def ibis_geometry_table() -> ibis_mod.Table:
    import ibis

    try:
        con = ibis.duckdb.connect(extensions=["spatial"])
    except Exception as e:  # extension download can fail offline
        pytest.skip(f"ibis duckdb spatial unavailable: {e}")
    con.raw_sql(
        "CREATE TABLE geo AS "
        "SELECT 1 AS a, ST_Point(1.0, 2.0) AS geom "
        "UNION ALL SELECT 2, NULL"
    )
    return con.table("geo")


# --- False positives (must never detect as geometry) -------------------


def false_positive_data() -> dict[str, list[Any]]:
    """Columns that look geometry-adjacent but are not geometry."""
    return {
        "raw_binary": [b"\x00\x01\x02", b"\xff\xfe", None],
        "wkt_looking": ["POINT (1 2)", "LINESTRING (0 0, 1 1)", None],
        # No None here: pandas would coerce the ints to float64, which
        # cannot represent H3 cell ids exactly.
        "h3_int": [H3_CELLS[0], H3_CELLS[1], H3_CELLS[0]],
    }


def pandas_shapely_object_column() -> Any:
    """Shapely objects in a plain object column, no GeoSeries."""
    import pandas as pd
    from shapely.geometry import Point

    return pd.DataFrame({"a": [1, 2], "obj": [Point(0, 0), Point(1, 1)]})


# --- Ordinary baselines ------------------------------------------------


def ordinary_data() -> dict[str, list[Any]]:
    """Small typed payload for ordinary-table baselines."""
    return {
        "int": [1, 2, 3],
        "float": [1.5, 2.5, 3.5],
        "str": ["a", "b", "c"],
        "bool": [True, False, True],
        "datetime": [
            datetime.datetime(2024, 1, 1),
            datetime.datetime(2024, 1, 2),
            datetime.datetime(2024, 1, 3),
        ],
    }

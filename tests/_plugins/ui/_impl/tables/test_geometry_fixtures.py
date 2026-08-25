# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import json

import pytest

from marimo._plugins.ui._impl.tables.utils import get_table_manager
from tests._plugins.ui._impl.tables import geometry_fixtures as geo
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


@pytest.mark.requires("geopandas")
class TestGeoPandasCharacterization:
    def test_preserves_geodataframe_on_ingest(self) -> None:
        import geopandas as gpd

        manager = get_table_manager(geo.gdf_point_known_crs())
        native = manager.data.to_native()
        assert isinstance(native, gpd.GeoDataFrame)

    def test_geometry_column_types_geometry(self) -> None:
        manager = get_table_manager(geo.gdf_point_known_crs())
        assert dict(manager.get_field_types()) == {
            "name": ("string", "str"),
            "geometry": ("geometry", "geometry"),
        }

    @pytest.mark.parametrize(
        ("make_frame", "expected_field_types"),
        [
            (
                geo.gdf_point_missing_crs,
                [
                    ("name", ("string", "str")),
                    ("geometry", ("geometry", "geometry")),
                ],
            ),
            (
                geo.gdf_multi_geometry,
                [
                    ("geom_a", ("geometry", "geometry")),
                    ("geom_b", ("geometry", "geometry")),
                ],
            ),
            (
                geo.gdf_no_active_geometry,
                [
                    ("a", ("integer", "int64")),
                    ("g", ("geometry", "geometry")),
                ],
            ),
            (
                geo.gdf_stale_pointer,
                [
                    ("name", ("string", "str")),
                    ("geom", ("geometry", "geometry")),
                ],
            ),
            (
                geo.gdf_dropped_active,
                [("geom_b", ("geometry", "geometry"))],
            ),
            (
                geo.gdf_with_null,
                [
                    ("name", ("string", "str")),
                    ("geometry", ("geometry", "geometry")),
                ],
            ),
            (
                geo.gdf_all_null,
                [
                    ("name", ("string", "str")),
                    ("geometry", ("geometry", "geometry")),
                ],
            ),
            (
                geo.gdf_mixed_types,
                [
                    ("name", ("string", "str")),
                    ("geometry", ("geometry", "geometry")),
                ],
            ),
            (
                geo.gdf_3d,
                [
                    ("name", ("string", "str")),
                    ("geometry", ("geometry", "geometry")),
                ],
            ),
        ],
    )
    def test_corpus_loads_and_serializes(
        self, make_frame, expected_field_types
    ) -> None:
        manager = get_table_manager(make_frame())
        assert manager.get_field_types() == expected_field_types
        assert isinstance(manager.to_json_str(), str)


@pytest.mark.requires("pyarrow")
class TestGeoArrowCharacterization:
    def test_wkb_types_geometry(self) -> None:
        manager = get_table_manager(geo.arrow_wkb_known_crs())
        assert dict(manager.get_field_types()) == {
            "a": ("integer", "Int64"),
            "geom": ("geometry", "geoarrow.wkb"),
        }

    def test_wkt_types_geometry(self) -> None:
        manager = get_table_manager(geo.arrow_wkt())
        assert dict(manager.get_field_types()) == {
            "a": ("integer", "Int64"),
            "geom": ("geometry", "geoarrow.wkt"),
        }

    @pytest.mark.parametrize(
        ("make_table", "expected_field_types"),
        [
            (
                geo.arrow_wkb_missing_crs,
                [
                    ("a", ("integer", "Int64")),
                    ("geom", ("geometry", "geoarrow.wkb")),
                ],
            ),
            (
                geo.arrow_ogc_wkb,
                [
                    ("a", ("integer", "Int64")),
                    ("geom", ("geometry", "ogc.wkb")),
                ],
            ),
            (
                geo.arrow_other_geoarrow,
                [
                    ("a", ("integer", "Int64")),
                    ("geom", ("geometry", "geoarrow.point")),
                ],
            ),
        ],
    )
    def test_corpus_loads_and_serializes(
        self, make_table, expected_field_types
    ) -> None:
        manager = get_table_manager(make_table())
        assert manager.get_field_types() == expected_field_types
        assert isinstance(manager.to_json_str(), str)


@pytest.mark.requires("duckdb", "polars")
class TestDuckDBCharacterization:
    def test_geometry_types_detected(self) -> None:
        conn = geo.duckdb_spatial_connection()
        try:
            relation = geo.duckdb_geometry_relation(conn)
            manager = get_table_manager(relation)
            field_types = dict(manager.get_field_types())
            assert field_types["a"][0] == "integer"
            assert field_types["geom"] == ("geometry", "GEOMETRY")
        finally:
            conn.close()


@pytest.mark.requires("ibis")
class TestIbisCharacterization:
    def test_geometry_types_unknown(self) -> None:
        table = geo.ibis_geometry_table()
        manager = get_table_manager(table)
        field_types = dict(manager.get_field_types())
        assert field_types["a"][0] == "integer"
        assert field_types["geom"] == ("unknown", "geospatial:geometry")


class TestFalsePositiveBaselines:
    """False-positive baselines for geometry detection regressions.

    If one changes, either detection behavior regressed or a serialization
    fix changed baseline output and should be called out in the PR.
    """

    @pytest.mark.requires("pandas")
    def test_pandas(self) -> None:
        import pandas as pd

        manager = get_table_manager(pd.DataFrame(geo.false_positive_data()))
        snapshot(
            "false_positives.pandas.field_types.json",
            json.dumps(manager.get_field_types()),
        )
        snapshot(
            "false_positives.pandas.json",
            manager.to_json_str(strict_json=True),
        )

    @pytest.mark.requires("polars")
    def test_polars(self) -> None:
        import polars as pl

        manager = get_table_manager(
            pl.DataFrame(geo.false_positive_data(), strict=False)
        )
        snapshot(
            "false_positives.polars.field_types.json",
            json.dumps(manager.get_field_types()),
        )
        snapshot("false_positives.polars.json", manager.to_json_str())

    @pytest.mark.requires("pyarrow")
    def test_pyarrow(self) -> None:
        import pyarrow as pa

        manager = get_table_manager(
            pa.Table.from_pydict(geo.false_positive_data())
        )
        snapshot(
            "false_positives.pyarrow.field_types.json",
            json.dumps(manager.get_field_types()),
        )
        snapshot("false_positives.pyarrow.json", manager.to_json_str())

    @pytest.mark.requires("geopandas")
    def test_shapely_objects_in_plain_column(self) -> None:
        manager = get_table_manager(geo.pandas_shapely_object_column())
        snapshot(
            "false_positives.shapely_objects.field_types.json",
            json.dumps(manager.get_field_types()),
        )


class TestOrdinaryBaselines:
    """Ordinary-table payload baselines for backends without one."""

    @pytest.mark.requires("pyarrow")
    def test_pyarrow(self) -> None:
        import pyarrow as pa

        manager = get_table_manager(pa.Table.from_pydict(geo.ordinary_data()))
        snapshot(
            "ordinary.pyarrow.field_types.json",
            json.dumps(manager.get_field_types()),
        )
        snapshot("ordinary.pyarrow.json", manager.to_json_str())

    @pytest.mark.requires("duckdb", "polars")
    def test_duckdb(self) -> None:
        import duckdb
        import polars as pl

        frame = pl.DataFrame(geo.ordinary_data())
        relation = duckdb.sql("SELECT * FROM frame")
        manager = get_table_manager(relation)
        snapshot(
            "ordinary.duckdb.field_types.json",
            json.dumps(manager.get_field_types()),
        )
        snapshot("ordinary.duckdb.json", manager.to_json_str())

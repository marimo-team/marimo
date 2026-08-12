# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import json
from typing import Any

import pytest

from marimo._plugins.ui._impl.tables.geometry import (
    GEOMETRY_CELL_CAP,
    GeometryColumnInfo,
    find_geometry_columns,
    format_geometry_cell,
)
from marimo._plugins.ui._impl.tables.narwhals_table import (
    NarwhalsTableManager,
)
from marimo._plugins.ui._impl.tables.utils import get_table_manager
from tests._plugins.ui._impl.tables import geometry_fixtures as geo


class TestFormatGeometryCell:
    def test_none_passes_through(self) -> None:
        assert format_geometry_cell(None, "objects") is None

    def test_wkb_placeholder(self) -> None:
        assert (
            format_geometry_cell(geo.WKB_POINT_1_2, "wkb")
            == f"<geometry, {len(geo.WKB_POINT_1_2)} B>"
        )

    def test_wkt_passthrough_and_cap(self) -> None:
        assert format_geometry_cell("POINT (1 2)", "wkt") == "POINT (1 2)"
        long = "POLYGON ((" + "1 2, " * 200 + "1 2))"
        capped = format_geometry_cell(long, "wkt")
        assert capped == long[:GEOMETRY_CELL_CAP] + "..."

    def test_other_passes_through(self) -> None:
        assert format_geometry_cell([1.0, 2.0], "other") == [1.0, 2.0]


@pytest.mark.requires("geopandas")
class TestPandasDetection:
    def test_detects_all_geometry_columns(self) -> None:
        import narwhals.stable.v2 as nw

        frame = nw.from_native(geo.gdf_multi_geometry(), eager_only=True)

        assert find_geometry_columns(frame) == {
            "geom_a": GeometryColumnInfo(
                encoding="objects", external_type="geometry"
            ),
            "geom_b": GeometryColumnInfo(
                encoding="objects", external_type="geometry"
            ),
        }

    def test_false_positives_not_detected(self) -> None:
        import narwhals.stable.v2 as nw

        frame = nw.from_native(
            geo.pandas_shapely_object_column(), eager_only=True
        )

        assert find_geometry_columns(frame) == {}


@pytest.mark.requires("pandas")
class TestNarwhalsGeometryContract:
    @staticmethod
    def _manager() -> NarwhalsTableManager[Any, Any]:
        import pandas as pd

        manager = NarwhalsTableManager.from_dataframe(
            pd.DataFrame(
                {
                    "name": ["a", "b"],
                    "geometry": ["POINT (0 0)", None],
                }
            )
        )
        manager.__dict__["_geometry_columns"] = {
            "geometry": GeometryColumnInfo(
                encoding="objects", external_type="geometry"
            )
        }
        return manager

    def test_semantic_type_overrides_dtype(self) -> None:
        manager = self._manager()

        assert manager.get_field_type("geometry") == ("geometry", "geometry")
        assert manager.get_field_type("name")[0] == "string"

    def test_search_skips_geometry(self) -> None:
        manager = self._manager()

        assert manager.search("POINT").get_num_rows() == 0

    def test_top_k_returns_empty(self) -> None:
        manager = self._manager()

        assert manager.calculate_top_k_rows("geometry", 10) == []

    def test_unique_values_returns_empty(self) -> None:
        manager = self._manager()

        assert manager.get_unique_column_values("geometry") == []

    def test_stats_counts_only(self) -> None:
        manager = self._manager()

        stats = manager.get_stats("geometry")
        assert stats.total == 2
        assert stats.nulls == 1
        assert stats.unique is None
        assert stats.min is None


@pytest.mark.requires("geopandas")
class TestGeoPandasManager:
    def test_field_type_uses_geometry_semantics(self) -> None:
        manager = get_table_manager(geo.gdf_point_known_crs())

        assert manager.get_field_type("geometry") == ("geometry", "geometry")

    def test_transforms_preserve_subclass_and_crs(self) -> None:
        import geopandas as gpd
        import narwhals.stable.v2 as nw

        manager = get_table_manager(geo.gdf_point_known_crs())
        data = manager.data
        for transformed in (
            data.filter(nw.col("name") == "a"),
            data.sort("name"),
            data.head(1),
            data.select(["name", "geometry"]),
        ):
            native = transformed.to_native()
            assert isinstance(native, gpd.GeoDataFrame)
            assert str(native.crs) == "EPSG:4326"

    def test_formatting_preserves_subclass_and_crs(self) -> None:
        import geopandas as gpd

        manager = get_table_manager(geo.gdf_point_known_crs())
        formatted = manager.apply_formatting({"name": str.upper})
        native = formatted.data.to_native()

        assert isinstance(native, gpd.GeoDataFrame)
        assert str(native.crs) == "EPSG:4326"

    def test_cells_render_capped_wkt(self) -> None:
        import geopandas as gpd
        from shapely.geometry import LineString

        geometry = LineString((index, index) for index in range(100))
        manager = get_table_manager(
            gpd.GeoDataFrame({"geometry": [geometry]}, geometry="geometry")
        )

        rows = json.loads(manager.to_json_str())
        assert rows[0]["geometry"] == (
            str(geometry)[:GEOMETRY_CELL_CAP] + "..."
        )

    def test_null_cell_stays_null(self) -> None:
        manager = get_table_manager(geo.gdf_with_null())

        rows = json.loads(manager.to_json_str())
        assert rows[1]["geometry"] is None

    def test_unique_values_returns_empty(self) -> None:
        manager = get_table_manager(geo.gdf_point_known_crs())

        assert manager.get_unique_column_values("geometry") == []


class TestManagerTemplateHook:
    @pytest.mark.requires("polars")
    def test_polars_uses_semantic_type(self) -> None:
        import polars as pl

        manager = get_table_manager(
            pl.DataFrame({"geometry": ["POINT (0 0)"]})
        )
        manager.__dict__["_geometry_columns"] = {
            "geometry": GeometryColumnInfo(
                encoding="wkt", external_type="geometry"
            )
        }

        assert manager.get_field_type("geometry") == ("geometry", "geometry")

    @pytest.mark.requires("ibis")
    def test_ibis_uses_semantic_type(self) -> None:
        import ibis

        manager = get_table_manager(
            ibis.memtable({"geometry": ["POINT (0 0)"]})
        )
        manager.__dict__["_geometry_columns"] = {
            "geometry": GeometryColumnInfo(
                encoding="wkt", external_type="geometry"
            )
        }

        assert manager.get_field_type("geometry") == ("geometry", "geometry")

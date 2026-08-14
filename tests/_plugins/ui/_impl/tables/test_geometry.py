# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import json
from typing import Any, Literal

import pytest

from marimo import _loggers
from marimo._plugins import ui
from marimo._plugins.ui._impl.dataframes.transforms.types import (
    FilterCondition,
    FilterGroup,
)
from marimo._plugins.ui._impl.table import (
    ColumnSummariesArgs,
    SearchTableArgs,
    SortArgs,
)
from marimo._plugins.ui._impl.tables.geometry import (
    GEOMETRY_CELL_CAP,
    GeometryColumnInfo,
    find_geometry_columns,
    format_geometry_cell,
)
from marimo._plugins.ui._impl.tables.narwhals_table import (
    NarwhalsTableManager,
)
from marimo._plugins.ui._impl.tables.table_manager import TableManager
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


@pytest.mark.requires("pyarrow")
class TestArrowDetection:
    def test_detects_wkb_extension(self) -> None:
        import narwhals.stable.v2 as nw

        frame = nw.from_native(geo.arrow_wkb_known_crs())

        assert find_geometry_columns(frame) == {
            "geom": GeometryColumnInfo(
                encoding="wkb", external_type="geoarrow.wkb"
            )
        }

    def test_detects_ogc_wkb_extension(self) -> None:
        import narwhals.stable.v2 as nw

        frame = nw.from_native(geo.arrow_ogc_wkb())

        assert find_geometry_columns(frame) == {
            "geom": GeometryColumnInfo(encoding="wkb", external_type="ogc.wkb")
        }

    def test_detects_wkt_extension(self) -> None:
        import narwhals.stable.v2 as nw

        frame = nw.from_native(geo.arrow_wkt())

        assert find_geometry_columns(frame) == {
            "geom": GeometryColumnInfo(
                encoding="wkt", external_type="geoarrow.wkt"
            )
        }

    def test_detects_other_geoarrow_extension(self) -> None:
        import narwhals.stable.v2 as nw

        frame = nw.from_native(geo.arrow_other_geoarrow())

        assert find_geometry_columns(frame) == {
            "geom": GeometryColumnInfo(
                encoding="other", external_type="geoarrow.point"
            )
        }

    def test_ignores_fields_without_extension_metadata(self) -> None:
        import narwhals.stable.v2 as nw
        import pyarrow as pa

        table = pa.table(geo.false_positive_data())

        assert find_geometry_columns(nw.from_native(table)) == {}

    def test_ignores_non_geo_extensions(self) -> None:
        import narwhals.stable.v2 as nw
        import pyarrow as pa

        field = pa.field(
            "u",
            pa.binary(),
            metadata={b"ARROW:extension:name": b"arrow.uuid"},
        )
        table = pa.table({"u": [b"x"]}, schema=pa.schema([field]))

        assert find_geometry_columns(nw.from_native(table)) == {}

    def test_manager_field_type_uses_geometry_semantics(self) -> None:
        manager = get_table_manager(geo.arrow_wkb_known_crs())

        assert manager.get_field_type("geom") == (
            "geometry",
            "geoarrow.wkb",
        )


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

        frame = geo.gdf_point_known_crs()
        frame["name"] = frame["name"].astype(object)
        manager = get_table_manager(frame)
        for transformed in (
            manager.sort_values([SortArgs(by="name", descending=True)]),
            manager.take(1, 0),
            manager.select_columns(["name", "geometry"]),
        ):
            native = transformed.data.to_native()
            assert isinstance(native, gpd.GeoDataFrame)
            assert str(native.crs) == "EPSG:4326"

    def test_host_filter_preserves_subclass_and_crs(self) -> None:
        import geopandas as gpd

        table = ui.table(geo.gdf_point_known_crs())
        filters = FilterGroup(
            children=(
                FilterCondition(
                    column_id="name",
                    operator="equals",
                    value="a",
                ),
            )
        )

        response = table._search(
            SearchTableArgs(
                page_size=10,
                page_number=0,
                filters=filters,
            )
        )
        native = table._searched_manager.data.to_native()

        assert response.total_rows == 1
        assert isinstance(native, gpd.GeoDataFrame)
        assert str(native.crs) == "EPSG:4326"

    def test_formatting_preserves_subclass_and_crs(self) -> None:
        import geopandas as gpd

        manager = get_table_manager(geo.gdf_point_known_crs())
        formatted = manager.apply_formatting({"name": str.upper})
        native = formatted.data.to_native()

        assert isinstance(native, gpd.GeoDataFrame)
        assert str(native.crs) == "EPSG:4326"

    def test_edge_frames_load_without_error(self) -> None:
        for make_frame in (
            geo.gdf_no_active_geometry,
            geo.gdf_stale_pointer,
            geo.gdf_dropped_active,
        ):
            manager = get_table_manager(make_frame())
            assert isinstance(manager.to_json_str(), str)

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

    def test_mixed_column_names_render_capped_wkt(self) -> None:
        import geopandas as gpd
        from shapely.geometry import LineString

        geometry = LineString((index, index) for index in range(100))
        frame = gpd.GeoDataFrame(
            {"name": ["a"], 1: gpd.GeoSeries([geometry])},
            geometry=1,
        )

        manager = get_table_manager(frame)
        rows = json.loads(manager.to_json_str())

        assert list(frame.columns) == ["name", 1]
        assert manager.get_column_names() == ["name", "1"]
        assert rows[0]["1"] == (str(geometry)[:GEOMETRY_CELL_CAP] + "...")

    def test_json_geometry_formatting_failure_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from marimo._plugins.ui._impl.tables import pandas_table

        manager = get_table_manager(geo.gdf_point_known_crs())

        def fail_formatting(*_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("intentional formatting failure")

        monkeypatch.setattr(
            pandas_table, "_format_geometry_columns", fail_formatting
        )

        rows = json.loads(manager.to_json_str())

        assert rows[0] == {"name": "a", "geometry": "POINT (0 0)"}

    def test_null_cell_stays_null(self) -> None:
        manager = get_table_manager(geo.gdf_with_null())

        rows = json.loads(manager.to_json_str())
        assert rows[1]["geometry"] is None

    @pytest.mark.requires("pyarrow", "geopandas")
    def test_arrow_cells_render_wkt_and_preserve_null(self) -> None:
        from pyarrow import ipc

        manager = get_table_manager(geo.gdf_with_null())

        rows = ipc.open_file(manager.to_arrow_ipc()).read_all().to_pylist()
        assert rows[0]["geometry"] == "POINT (0 0)"
        assert rows[1]["geometry"] is None

    @pytest.mark.requires("pyarrow", "geopandas")
    def test_arrow_detection_miss_degrades_to_strings(self) -> None:
        from pyarrow import ipc

        manager = get_table_manager(geo.gdf_with_null())
        manager.__dict__["_geometry_columns"] = {}

        rows = ipc.open_file(manager.to_arrow_ipc()).read_all().to_pylist()

        assert rows[0]["geometry"] == "POINT (0 0)"
        assert rows[1]["geometry"] is None

    def test_unique_values_returns_empty(self) -> None:
        manager = get_table_manager(geo.gdf_point_known_crs())

        assert manager.get_unique_column_values("geometry") == []

    def test_search_skips_geometry(self) -> None:
        manager = get_table_manager(geo.gdf_point_known_crs())

        assert manager.search("POINT").get_num_rows() == 0

    def test_top_k_returns_empty(self) -> None:
        manager = get_table_manager(geo.gdf_point_known_crs())

        assert manager.calculate_top_k_rows("geometry", 10) == []

    def test_stats_counts_only(self) -> None:
        manager = get_table_manager(geo.gdf_with_null())

        stats = manager.get_stats("geometry")
        assert stats.total == 2
        assert stats.nulls == 1
        assert stats.unique is None
        assert stats.min is None


@pytest.mark.requires("geopandas")
class TestHostGuards:
    def test_chart_fallback_drops_geometry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        frame = geo.gdf_point_known_crs().assign(value=[1, 2])
        table = ui.table(frame, show_column_summaries=True)

        def fail_bin_values(*_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("Intentional bin failure")

        def column_names_as_chart_data(
            manager: TableManager[Any],
        ) -> tuple[str, Literal["csv"]]:
            return ",".join(manager.get_column_names()), "csv"

        monkeypatch.setattr(table._manager, "get_bin_values", fail_bin_values)
        monkeypatch.setattr(
            type(table),
            "_to_chart_data_url",
            staticmethod(column_names_as_chart_data),
        )

        summaries = table._get_column_summaries(ColumnSummariesArgs())

        assert summaries.data == "name,value"

    def test_sort_is_ignored(self) -> None:
        table = ui.table(geo.gdf_point_known_crs())

        with _loggers.capture_output() as (_, _, records):
            response = table._search(
                SearchTableArgs(
                    page_size=10,
                    page_number=0,
                    sort=[SortArgs(by="geometry", descending=True)],
                )
            )

        rows = json.loads(response.data)
        assert [row["name"] for row in rows] == ["a", "b"]
        assert any(
            record.getMessage()
            == "Ignoring sort on geometry column 'geometry'"
            for record in records
        )

    def test_filter_is_ignored(self) -> None:
        table = ui.table(geo.gdf_point_known_crs(), selection=None)
        filters = FilterGroup(
            children=(
                FilterCondition(
                    column_id="geometry",
                    operator="contains",
                    value="POINT",
                ),
            )
        )

        with _loggers.capture_output() as (_, _, records):
            response = table._search(
                SearchTableArgs(
                    page_size=10,
                    page_number=0,
                    filters=filters,
                )
            )

        assert response.total_rows == 2
        assert any(
            record.getMessage()
            == "Ignoring filter on geometry column 'geometry'"
            for record in records
        )


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

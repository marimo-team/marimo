# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal
from unittest.mock import patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.table import DownloadAsArgs, DownloadAsResponse
from marimo._plugins.ui._impl.tables.narwhals_table import NarwhalsTableManager
from marimo._runtime.functions import EmptyArgs
from marimo._utils.parse_dataclass import parse_raw
from tests._plugins.ui._impl.tables import geometry_fixtures as fixtures


@pytest.fixture(params=[ui.table, ui.dataframe], ids=["table", "dataframe"])
def widget(request: pytest.FixtureRequest) -> Any:
    return request.param


@pytest.mark.requires("geopandas", "pyarrow")
def test_multigeometry_metadata_does_not_read_rows(widget: Any) -> None:
    source = fixtures.gdf_multi_geometry()
    subject = widget(source)
    with (
        patch.object(
            NarwhalsTableManager,
            "as_frame",
            side_effect=AssertionError("Metadata must not collect rows"),
        ),
        patch.object(
            NarwhalsTableManager,
            "to_json_str",
            side_effect=AssertionError("Metadata must not serialize rows"),
        ),
    ):
        result = subject._get_export_metadata(EmptyArgs())

    assert asdict(result) == {
        "geometry_columns": [
            {"name": "geom_a", "encoding": "objects", "crs": "EPSG:4326"},
            {"name": "geom_b", "encoding": "objects", "crs": "EPSG:3857"},
        ],
        "primary_geometry_column": "geom_a",
        "default_geometry_column": "geom_a",
        "formats": {
            "geojson": {
                "available": True,
                "reason": None,
                "missing_packages": [],
            },
            "parquet": {
                "available": True,
                "reason": None,
                "missing_packages": [],
            },
        },
    }
    assert source.geometry.name == "geom_a"


@pytest.mark.requires("geopandas")
@pytest.mark.parametrize(
    ("factory", "primary", "default"),
    [
        (fixtures.gdf_no_active_geometry, None, "g"),
        (fixtures.gdf_stale_pointer, None, "geom"),
        (fixtures.gdf_dropped_active, None, "geom_b"),
    ],
)
def test_stale_or_missing_primary_uses_sole_geometry(
    widget: Any, factory: Any, primary: str | None, default: str
) -> None:
    result = widget(factory())._get_export_metadata(EmptyArgs())
    assert (
        result.primary_geometry_column,
        result.default_geometry_column,
    ) == (
        primary,
        default,
    )


@pytest.mark.requires("geopandas")
def test_ambiguous_geometry_has_no_default(widget: Any) -> None:
    import pandas as pd

    result = widget(
        pd.DataFrame(fixtures.gdf_multi_geometry())
    )._get_export_metadata(EmptyArgs())
    assert [column.name for column in result.geometry_columns] == [
        "geom_a",
        "geom_b",
    ]
    assert result.primary_geometry_column is None
    assert result.default_geometry_column is None
    assert result.formats["geojson"].available


@pytest.mark.requires("geopandas")
def test_old_geopandas_blocks_only_geoparquet(widget: Any) -> None:
    with patch.object(
        DependencyManager.geopandas, "get_version", return_value="0.14.0"
    ):
        result = widget(fixtures.gdf_multi_geometry())._get_export_metadata(
            EmptyArgs()
        )

    assert asdict(result.formats["parquet"]) == {
        "available": False,
        "reason": "Update geopandas to 0.14.1 or newer to export GeoParquet.",
        "missing_packages": [],
    }
    assert result.formats["geojson"].available


@pytest.mark.requires("geopandas")
def test_empty_name_can_be_the_source_primary(widget: Any) -> None:
    source = fixtures.gdf_multi_geometry().rename(columns={"geom_b": ""})
    source = source.set_geometry("")
    result = widget(source)._get_export_metadata(EmptyArgs())
    assert result.primary_geometry_column == ""
    assert result.default_geometry_column == ""
    assert result.formats["geojson"].available


@pytest.mark.requires("geopandas")
def test_empty_geometry_retains_unknown_crs(widget: Any) -> None:
    source = fixtures.gdf_all_null().head(0)
    result = widget(source)._get_export_metadata(EmptyArgs())
    assert [asdict(column) for column in result.geometry_columns] == [
        {"name": "geometry", "encoding": "objects", "crs": None},
    ]


@pytest.mark.requires("geopandas")
def test_missing_pyarrow_is_reported(widget: Any) -> None:
    subject = widget(fixtures.gdf_multi_geometry())
    with patch.object(DependencyManager.pyarrow, "has", return_value=False):
        result = subject._get_export_metadata(EmptyArgs())
    assert asdict(result.formats["parquet"]) == {
        "available": False,
        "reason": "GeoParquet export requires pyarrow.",
        "missing_packages": ["pyarrow"],
    }
    assert asdict(result.formats["geojson"]) == {
        "available": True,
        "reason": None,
        "missing_packages": [],
    }


@pytest.mark.requires("geopandas")
def test_missing_geopandas_is_reported(widget: Any) -> None:
    subject = widget(fixtures.gdf_multi_geometry())
    with patch.object(DependencyManager.geopandas, "has", return_value=False):
        result = subject._get_export_metadata(EmptyArgs())
    assert asdict(result.formats["parquet"]) == {
        "available": False,
        "reason": "This pandas table needs geopandas to export GeoParquet.",
        "missing_packages": ["geopandas"],
    }
    assert asdict(result.formats["geojson"]) == {
        "available": False,
        "reason": "This pandas table needs geopandas to export GeoJSON.",
        "missing_packages": ["geopandas"],
    }


@pytest.mark.requires("pyarrow")
def test_arrow_crs_comes_from_field_metadata(widget: Any) -> None:
    subject = widget(fixtures.arrow_wkb_known_crs())
    result = subject._get_export_metadata(EmptyArgs())
    assert [asdict(column) for column in result.geometry_columns] == [
        {"name": "geom", "encoding": "wkb", "crs": "EPSG:4326"},
    ]
    assert asdict(result.formats["parquet"]) == {
        "available": False,
        "reason": "GeoParquet export from Arrow tables is not supported yet.",
        "missing_packages": [],
    }
    assert asdict(result.formats["geojson"]) == {
        "available": False,
        "reason": "GeoJSON export from Arrow tables is not supported yet.",
        "missing_packages": [],
    }


@pytest.mark.requires("geopandas")
@pytest.mark.parametrize("empty", [False, True])
def test_geojson_support_does_not_depend_on_default_crs(
    widget: Any, empty: bool
) -> None:
    import geopandas as gpd  # type: ignore[import-untyped]

    source = fixtures.gdf_multi_geometry()
    source = gpd.GeoDataFrame(
        {
            "geom_a": gpd.GeoSeries(list(source["geom_a"])),
            "geom_b": source["geom_b"],
        },
        geometry="geom_a",
    )
    if empty:
        source = source.head(0)
    subject = widget(source)
    with patch.object(
        gpd.GeoSeries,
        "to_crs",
        side_effect=AssertionError("Metadata must not reproject geometry"),
    ):
        result = subject._get_export_metadata(EmptyArgs())
    assert result.default_geometry_column == "geom_a"
    assert [column.crs for column in result.geometry_columns] == [
        None,
        "EPSG:3857",
    ]
    assert result.formats["geojson"].available


@pytest.mark.requires("pandas")
def test_ordinary_metadata_needs_no_geospatial_packages(widget: Any) -> None:
    import pandas as pd

    subject = widget(pd.DataFrame({"geometry": ["POINT (1 2)"]}))
    with patch.object(DependencyManager.geopandas, "has", return_value=False):
        assert asdict(subject._get_export_metadata(EmptyArgs())) == {
            "geometry_columns": [],
            "primary_geometry_column": None,
            "default_geometry_column": None,
            "formats": {},
        }


@pytest.mark.requires("geopandas")
def test_table_metadata_includes_columns_outside_the_preview() -> None:
    subject = ui.table(
        fixtures.gdf_multi_geometry(),
        max_columns=1,
        hidden_columns=["geom_b"],
    )
    result = subject._get_export_metadata(EmptyArgs())
    assert [column.name for column in result.geometry_columns] == [
        "geom_a",
        "geom_b",
    ]


@pytest.mark.requires("geopandas")
def test_dataframe_metadata_follows_transformed_columns() -> None:
    subject = ui.dataframe(fixtures.gdf_multi_geometry())
    subject._update(
        {"transforms": [{"type": "select_columns", "column_ids": ["geom_b"]}]}
    )
    result = subject._get_export_metadata(EmptyArgs())
    assert [column.name for column in result.geometry_columns] == ["geom_b"]
    assert result.default_geometry_column == "geom_b"


@pytest.mark.parametrize(
    "payload",
    [
        {"format": "parquet"},
        {"format": "parquet", "geometry_column": "geom_b"},
        {"format": "geojson"},
        {"format": "geojson", "geometry_column": "geom_b"},
        {"format": "geojson", "geometry_column": ""},
        {"format": "csv", "options": {"separator": ";"}},
    ],
)
def test_download_request_accepts_optional_geometry(
    payload: dict[str, Any],
) -> None:
    parsed = parse_raw(payload, DownloadAsArgs)
    assert parsed.geometry_column == payload.get("geometry_column")
    assert parsed.format == payload["format"]


def test_download_response_accepts_missing_crs() -> None:
    parsed = parse_raw(
        {"code": "missing_crs", "column": "", "error": "Declare a CRS."},
        DownloadAsResponse,
    )
    assert parsed.code == "missing_crs"
    assert parsed.column == ""


@pytest.mark.requires("geopandas")
@pytest.mark.parametrize("request_format", ["parquet", "geojson"])
def test_widget_passes_geometry_request_to_export(
    widget: Any, request_format: Literal["parquet", "geojson"]
) -> None:
    subject = widget(fixtures.gdf_multi_geometry())
    module = (
        "marimo._plugins.ui._impl.table"
        if widget is ui.table
        else "marimo._plugins.ui._impl.dataframes.dataframe"
    )
    with patch(
        f"{module}.download_as",
        return_value=("data:test", f"test.{request_format}"),
    ) as export:
        response = subject._download_as(
            DownloadAsArgs(format=request_format, geometry_column="geom_b")
        )
    assert response.url == "data:test"
    assert export.call_args.kwargs["geometry_column"] == "geom_b"

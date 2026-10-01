# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.table import DownloadAsArgs
from marimo._runtime.functions import EmptyArgs
from marimo._utils.data_uri import from_data_uri
from tests._plugins.ui._impl.tables import geometry_fixtures as fixtures


@pytest.fixture(params=[ui.table, ui.dataframe], ids=["table", "dataframe"])
def widget(request: pytest.FixtureRequest) -> Any:
    return request.param


def _artifact(
    widget: Any, geometry_column: str | None = None
) -> tuple[bytes, str]:
    response = widget._download_as(
        DownloadAsArgs(format="parquet", geometry_column=geometry_column)
    )
    assert response.error is None
    return from_data_uri(response.url)[1], response.filename


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("choice", [None, "geom_b"])
def test_geoparquet_keeps_every_geometry_and_crs(
    widget: Any, choice: str | None
) -> None:
    import geopandas as gpd
    import pyarrow as pa
    import pyarrow.parquet as pq
    from pyproj import CRS

    source = fixtures.gdf_multi_geometry()
    original = source.copy(deep=True)
    artifact, filename = _artifact(widget(source), choice)
    reader = pq.ParquetFile(io.BytesIO(artifact))
    geo = json.loads(reader.metadata.metadata[b"geo"])
    primary = choice or "geom_a"

    assert filename.endswith(".parquet")
    assert geo["version"] == "1.0.0"
    assert geo["primary_column"] == primary
    assert set(geo["columns"]) == {"geom_a", "geom_b"}
    table = reader.read()
    for name in ("geom_a", "geom_b"):
        assert geo["columns"][name]["encoding"] == "WKB"
        assert (
            CRS.from_json_dict(geo["columns"][name]["crs"]) == source[name].crs
        )
        assert pa.types.is_binary(table.schema.field(name).type)
        assert table[name][0].as_py() == source[name].iloc[0].wkb

    restored = gpd.read_parquet(io.BytesIO(artifact))
    assert restored.geometry.name == primary
    assert restored["geom_a"].crs == source["geom_a"].crs
    assert restored["geom_b"].crs == source["geom_b"].crs
    assert source.geometry.name == "geom_a"
    assert source.equals(original)


@pytest.mark.requires("geopandas", "pyarrow")
def test_geoparquet_uses_writer_supported_by_geopandas_014(
    widget: Any,
) -> None:
    import geopandas as gpd
    import pyarrow.parquet as pq

    original_writer = gpd.GeoDataFrame.to_parquet

    def old_writer(
        self: Any,
        path: Any,
        *,
        index: bool | None = None,
        schema_version: str | None = None,
    ) -> None:
        original_writer(self, path, index=index, schema_version=schema_version)

    with patch.object(gpd.GeoDataFrame, "to_parquet", old_writer):
        artifact, _ = _artifact(widget(fixtures.gdf_multi_geometry()))

    geo = json.loads(pq.read_metadata(io.BytesIO(artifact)).metadata[b"geo"])
    assert geo["version"] == "1.0.0"
    assert all(
        column["encoding"] == "WKB" for column in geo["columns"].values()
    )


@pytest.mark.requires("geopandas", "pyarrow")
def test_empty_name_is_a_valid_explicit_primary(widget: Any) -> None:
    import pyarrow.parquet as pq

    source = fixtures.gdf_multi_geometry().rename(columns={"geom_b": ""})
    artifact, _ = _artifact(widget(source), "")
    geo = json.loads(pq.read_metadata(io.BytesIO(artifact)).metadata[b"geo"])
    assert geo["primary_column"] == ""
    assert set(geo["columns"]) == {"geom_a", ""}


@pytest.mark.requires("geopandas", "pyarrow")
def test_ambiguous_pandas_geometry_requires_choice(widget: Any) -> None:
    import pandas as pd

    source = pd.DataFrame(fixtures.gdf_multi_geometry())
    subject = widget(source)
    response = subject._download_as(DownloadAsArgs(format="parquet"))
    assert (
        response.url,
        response.filename,
        response.code,
        response.column,
    ) == (
        "",
        "",
        "geometry_required",
        None,
    )
    artifact, _ = _artifact(subject, "geom_b")
    import pyarrow.parquet as pq

    geo = json.loads(pq.read_metadata(io.BytesIO(artifact)).metadata[b"geo"])
    assert geo["primary_column"] == "geom_b"
    assert not hasattr(source, "_geometry_column_name")


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize(
    "factory",
    [fixtures.gdf_no_active_geometry, fixtures.gdf_stale_pointer],
)
def test_sole_geometry_survives_missing_or_stale_primary(
    widget: Any, factory: Any
) -> None:
    import pyarrow.parquet as pq

    source = factory()
    artifact, _ = _artifact(widget(source))
    geo = json.loads(pq.read_metadata(io.BytesIO(artifact)).metadata[b"geo"])
    assert geo["primary_column"] in {"g", "geom"}


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("empty", [False, True])
def test_unknown_crs_is_explicit_for_empty_or_null_geometry(
    widget: Any, empty: bool
) -> None:
    import pyarrow.parquet as pq

    source = fixtures.gdf_all_null()
    if empty:
        source = source.head(0)
    artifact, _ = _artifact(widget(source))
    reader = pq.ParquetFile(io.BytesIO(artifact))
    geo = json.loads(reader.metadata.metadata[b"geo"])
    assert geo["columns"]["geometry"]["crs"] is None
    assert reader.metadata.num_rows == len(source)


@pytest.mark.requires("geopandas", "pyarrow")
def test_geoparquet_keeps_supported_z_geometry(widget: Any) -> None:
    import pyarrow.parquet as pq

    artifact, _ = _artifact(widget(fixtures.gdf_3d()))
    geo = json.loads(pq.read_metadata(io.BytesIO(artifact)).metadata[b"geo"])
    assert "Point Z" in geo["columns"]["geometry"]["geometry_types"]


@pytest.mark.requires("geopandas", "pyarrow")
def test_geoparquet_rejects_unsupported_m_geometry(widget: Any) -> None:
    import geopandas as gpd
    from shapely import from_wkt

    source = gpd.GeoDataFrame(
        {"geometry": [from_wkt("POINT M (1 2 3)")]}, geometry="geometry"
    )
    response = widget(source)._download_as(DownloadAsArgs(format="parquet"))
    assert (
        response.url,
        response.filename,
        response.code,
        response.column,
    ) == (
        "",
        "",
        "unsupported_representation",
        "geometry",
    )


@pytest.mark.requires("geopandas", "pyarrow")
def test_invalid_geometry_choice_publishes_no_artifact(widget: Any) -> None:
    subject = widget(fixtures.gdf_multi_geometry())
    with patch(
        "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
    ) as publish:
        response = subject._download_as(
            DownloadAsArgs(format="parquet", geometry_column="missing")
        )
    assert (
        response.url,
        response.filename,
        response.code,
        response.column,
    ) == (
        "",
        "",
        "invalid_geometry",
        "missing",
    )
    publish.assert_not_called()


@pytest.mark.requires("geopandas")
def test_missing_pyarrow_is_a_structured_failure(widget: Any) -> None:
    subject = widget(fixtures.gdf_multi_geometry())
    with patch.object(DependencyManager.pyarrow, "has", return_value=False):
        response = subject._download_as(DownloadAsArgs(format="parquet"))
    assert (response.url, response.code, response.missing_packages) == (
        "",
        "missing_packages",
        ["pyarrow"],
    )


@pytest.mark.requires("pyarrow")
def test_declared_arrow_geometry_is_not_labeled_geoparquet(
    widget: Any,
) -> None:
    response = widget(fixtures.arrow_wkb_known_crs())._download_as(
        DownloadAsArgs(format="parquet")
    )
    assert response.code == "unsupported_representation"
    assert response.url == ""


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("choice", [None, "geom_b"])
def test_table_exports_only_selected_rows(choice: str | None) -> None:
    import pyarrow.parquet as pq

    subject = ui.table(fixtures.gdf_multi_geometry(), selection="multi")
    subject._convert_value(["1"])
    artifact, _ = _artifact(subject, choice)
    table = pq.read_table(io.BytesIO(artifact))
    assert table.num_rows == 1
    assert table["geom_b"][0].as_py() == subject.data["geom_b"].iloc[1].wkb
    geo = json.loads(pq.read_metadata(io.BytesIO(artifact)).metadata[b"geo"])
    assert geo["primary_column"] == (choice or "geom_a")


@pytest.mark.requires("geopandas", "pyarrow")
def test_dataframe_exports_current_value() -> None:
    import pyarrow.parquet as pq

    source = fixtures.gdf_multi_geometry()
    subject = ui.dataframe(source)
    subject._value = source.iloc[[1]].copy()
    artifact, _ = _artifact(subject, "geom_b")
    table = pq.read_table(io.BytesIO(artifact))
    assert table.num_rows == 1
    assert table["geom_b"][0].as_py() == source["geom_b"].iloc[1].wkb


@pytest.mark.requires("geopandas", "pyarrow")
def test_dataframe_exports_transformed_geometry_columns() -> None:
    import pyarrow.parquet as pq

    subject = ui.dataframe(fixtures.gdf_multi_geometry())
    subject._update(
        {"transforms": [{"type": "select_columns", "column_ids": ["geom_b"]}]}
    )
    artifact, _ = _artifact(subject)
    reader = pq.ParquetFile(io.BytesIO(artifact))
    geo = json.loads(reader.metadata.metadata[b"geo"])
    assert geo["primary_column"] == "geom_b"
    assert set(geo["columns"]) == {"geom_b"}


@pytest.mark.requires("geopandas", "pyarrow")
def test_stale_choice_is_rejected_after_dataframe_source_changes() -> None:
    source = fixtures.gdf_multi_geometry()
    subject = ui.dataframe(source)
    assert len(subject._get_export_metadata(EmptyArgs()).geometry_columns) == 2
    subject._value = source.drop(columns=["geom_b"])
    response = subject._download_as(
        DownloadAsArgs(format="parquet", geometry_column="geom_b")
    )
    assert (response.url, response.code, response.column) == (
        "",
        "invalid_geometry",
        "geom_b",
    )


@pytest.mark.requires("geopandas", "pyarrow")
def test_malformed_writer_output_publishes_no_artifact(widget: Any) -> None:
    import geopandas as gpd
    import pyarrow as pa
    import pyarrow.parquet as pq

    def write_plain_parquet(_source: Any, path: Any, **_kwargs: Any) -> None:
        pq.write_table(pa.table({"geom_a": [b"invalid"]}), path)

    subject = widget(fixtures.gdf_multi_geometry())
    with (
        patch.object(gpd.GeoDataFrame, "to_parquet", write_plain_parquet),
        patch(
            "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
        ) as publish,
    ):
        response = subject._download_as(DownloadAsArgs(format="parquet"))
    assert (response.url, response.filename, response.code) == (
        "",
        "",
        "invalid_metadata",
    )
    publish.assert_not_called()


@pytest.mark.requires("geopandas", "pyarrow")
def test_writer_failure_publishes_no_artifact(widget: Any) -> None:
    import geopandas as gpd

    subject = widget(fixtures.gdf_multi_geometry())
    with (
        patch.object(
            gpd.GeoDataFrame,
            "to_parquet",
            side_effect=ValueError("invalid geometry value"),
        ),
        patch(
            "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
        ) as publish,
    ):
        response = subject._download_as(DownloadAsArgs(format="parquet"))
    assert (response.url, response.filename, response.code) == (
        "",
        "",
        "conversion_failed",
    )
    publish.assert_not_called()


@pytest.mark.requires("pandas", "pyarrow")
@pytest.mark.parametrize("format_type", ["parquet", "csv"])
def test_ordinary_formats_reject_a_geometry_choice(
    widget: Any, format_type: str
) -> None:
    import pandas as pd

    subject = widget(pd.DataFrame({"value": [1, 2]}))
    response = subject._download_as(
        DownloadAsArgs(format=format_type, geometry_column="value")
    )
    assert (response.url, response.code, response.column) == (
        "",
        "invalid_geometry",
        "value",
    )


@pytest.mark.requires("pandas", "pyarrow")
def test_ordinary_parquet_bytes_remain_unchanged() -> None:
    import pandas as pd

    subject = ui.dataframe(pd.DataFrame({"value": [1, 2], "name": ["a", "b"]}))
    expected = subject._get_cached_table_manager(
        subject._value, None
    ).to_parquet()
    artifact, _ = _artifact(subject)
    assert artifact == expected

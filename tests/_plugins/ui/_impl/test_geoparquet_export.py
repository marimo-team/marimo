# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
import json
from typing import Any, Literal
from unittest.mock import patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.table import DownloadAsArgs
from marimo._plugins.ui._impl.tables.geometry_export import (
    ExportFormatEligibility,
    GeometryExportColumn,
)
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
@pytest.mark.parametrize("arrow", [False, True], ids=["pandas", "arrow"])
def test_geoparquet_uses_writer_supported_by_geopandas_0141(
    widget: Any,
    arrow: bool,
) -> None:
    import geopandas as gpd
    import pyarrow.parquet as pq

    original_writer = gpd.GeoDataFrame.to_parquet

    def compatible_writer(
        self: Any,
        path: Any,
        *,
        index: bool | None = None,
        schema_version: str | None = None,
    ) -> None:
        original_writer(self, path, index=index, schema_version=schema_version)

    with patch.object(gpd.GeoDataFrame, "to_parquet", compatible_writer):
        source = (
            fixtures.arrow_multi_geometry()
            if arrow
            else fixtures.gdf_multi_geometry()
        )
        artifact, _ = _artifact(widget(source), "geom_a")

    geo = json.loads(pq.read_metadata(io.BytesIO(artifact)).metadata[b"geo"])
    assert geo["version"] == "1.0.0"
    assert all(
        column["encoding"] == "WKB" for column in geo["columns"].values()
    )


@pytest.mark.requires("geopandas")
def test_geoparquet_rejects_old_geopandas(widget: Any) -> None:
    with patch.object(
        DependencyManager.geopandas, "get_version", return_value="0.14.0"
    ):
        response = widget(fixtures.gdf_multi_geometry())._download_as(
            DownloadAsArgs(format="parquet")
        )

    assert response.url == ""
    assert response.code == "unsupported_version"
    assert (
        response.error
        == "Update geopandas to 0.14.1 or newer to export GeoParquet."
    )
    assert response.missing_packages is None


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

    geometry = from_wkt("POINT M (1 2 3)")
    if not getattr(geometry, "has_m", False):
        pytest.skip("Installed Shapely cannot represent M coordinates")
    source = gpd.GeoDataFrame({"geometry": [geometry]}, geometry="geometry")
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


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize(
    "factory",
    [
        fixtures.arrow_wkb_known_crs,
        fixtures.arrow_wkt,
        fixtures.arrow_multi_geometry,
        fixtures.arrow_wkb_projected,
        fixtures.arrow_invalid_wkb,
    ],
)
def test_declared_arrow_geometry_is_eligible_for_geoparquet(
    widget: Any, factory: Any
) -> None:
    metadata = widget(factory())._get_export_metadata(EmptyArgs())
    assert metadata.formats["parquet"] == ExportFormatEligibility(
        available=True
    )


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize(
    ("factory", "reason"),
    [
        (fixtures.arrow_malformed_metadata, "invalid GeoArrow metadata"),
        (fixtures.arrow_spherical_edges, "edges"),
        (fixtures.arrow_other_geoarrow, "native GeoArrow layout"),
    ],
)
def test_arrow_declaration_blocks_both_geographic_formats(
    widget: Any, factory: Any, reason: str
) -> None:
    metadata = widget(factory())._get_export_metadata(EmptyArgs())
    for format_name in ("parquet", "geojson"):
        eligibility = metadata.formats[format_name]
        assert not eligibility.available
        assert eligibility.reason is not None
        assert reason in eligibility.reason
        assert eligibility.missing_packages == []


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (b"not json", "expected a UTF-8 JSON object"),
        (b"\xff", "expected a UTF-8 JSON object"),
        (b"null", "expected a JSON object"),
        (b'{"crs":null}', "crs must be a string or PROJJSON object"),
        (b'{"crs":4326}', "crs must be a string or PROJJSON object"),
        (b'{"crs":[]}', "crs must be a string or PROJJSON object"),
        (b'{"crs":"not a CRS"}', "crs cannot be resolved"),
        (b'{"crs":{}}', "crs cannot be resolved"),
        (b'{"crs_type":"unknown"}', "unknown crs_type"),
        (b'{"crs_type":[]}', "unknown crs_type"),
        (b'{"crs_type":null}', "unknown crs_type"),
        (b'{"edges":"planar"}', "unknown edges interpretation"),
        (b'{"edges":null}', "unknown edges interpretation"),
        (b'{"edges":{}}', "unknown edges interpretation"),
    ],
)
def test_invalid_arrow_metadata_reports_a_reason(
    widget: Any, raw: bytes, reason: str
) -> None:
    source = fixtures.arrow_wkb_known_crs()
    field = source.schema.field("geom").with_metadata(
        {
            b"ARROW:extension:name": b"geoarrow.wkb",
            b"ARROW:extension:metadata": raw,
        }
    )
    source = source.cast(source.schema.set(1, field))
    metadata = widget(source)._get_export_metadata(EmptyArgs())
    expected = ExportFormatEligibility(
        available=False,
        reason=f"Geometry column 'geom' has invalid GeoArrow metadata: {reason}.",
    )
    assert metadata.formats == {"parquet": expected, "geojson": expected}


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize(
    "edges", ["spherical", "vincenty", "thomas", "andoyer", "karney"]
)
def test_arrow_secondary_edges_block_both_formats(
    widget: Any, edges: str
) -> None:
    source = fixtures.arrow_multi_geometry()
    field = source.schema.field("geom_b").with_metadata(
        {
            b"ARROW:extension:name": b"geoarrow.wkt",
            b"ARROW:extension:metadata": json.dumps(
                {"crs": "EPSG:4326", "edges": edges}
            ).encode(),
        }
    )
    source = source.cast(source.schema.set(2, field))
    metadata = widget(source)._get_export_metadata(EmptyArgs())
    expected = ExportFormatEligibility(
        available=False,
        reason=f"Geometry column 'geom_b' declares {edges!r} edges, "
        "which geographic exports cannot preserve.",
    )
    assert metadata.formats == {"parquet": expected, "geojson": expected}


@pytest.mark.requires("geopandas", "pyarrow")
def test_arrow_secondary_native_geometry_blocks_both_formats(
    widget: Any,
) -> None:
    source = fixtures.arrow_wkb_known_crs()
    other = fixtures.arrow_other_geoarrow()
    source = source.append_column(
        other.schema.field("geom").with_name("native"), other["geom"]
    )
    metadata = widget(source)._get_export_metadata(EmptyArgs())
    expected = ExportFormatEligibility(
        available=False,
        reason="Geometry column 'native' uses a native GeoArrow layout. "
        "Geographic exports require WKB or WKT.",
    )
    assert metadata.formats == {"parquet": expected, "geojson": expected}


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize(
    "factory", [fixtures.arrow_wkb_missing_crs, fixtures.arrow_srid_crs]
)
def test_arrow_unknown_crs_stays_unknown(widget: Any, factory: Any) -> None:
    metadata = widget(factory())._get_export_metadata(EmptyArgs())
    assert metadata.geometry_columns == [
        GeometryExportColumn(name="geom", encoding="wkb", crs=None)
    ]
    assert metadata.primary_geometry_column is None
    assert metadata.default_geometry_column == "geom"
    assert metadata.formats["parquet"] == ExportFormatEligibility(
        available=True
    )


@pytest.mark.requires("geopandas", "pyarrow")
def test_arrow_metadata_keeps_separate_crs_without_parsing_values(
    widget: Any,
) -> None:
    import geopandas as gpd
    import narwhals.stable.v2 as nw
    from pyproj import CRS

    subject = widget(fixtures.arrow_multi_geometry())
    with (
        patch.object(
            nw.DataFrame,
            "to_pandas",
            side_effect=AssertionError("materialized rows"),
        ),
        patch.object(
            nw.DataFrame,
            "to_dict",
            side_effect=AssertionError("materialized rows"),
        ),
        patch.object(
            gpd.GeoSeries,
            "from_wkb",
            side_effect=AssertionError("materialized WKB"),
        ),
        patch.object(
            gpd.GeoSeries,
            "from_wkt",
            side_effect=AssertionError("materialized WKT"),
        ),
    ):
        metadata = subject._get_export_metadata(EmptyArgs())
    assert metadata.geometry_columns == [
        GeometryExportColumn(name="geom_a", encoding="wkb", crs="EPSG:3857"),
        GeometryExportColumn(
            name="geom_b",
            encoding="wkt",
            crs=CRS.from_epsg(4326).to_json_dict(),
        ),
    ]
    assert metadata.primary_geometry_column is None
    assert metadata.default_geometry_column is None


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize(
    "crs_type", [None, "projjson", "wkt2:2019", "authority_code"]
)
def test_arrow_crs_representations_are_eligible(
    widget: Any, crs_type: str | None
) -> None:
    from pyproj import CRS

    crs = CRS.from_epsg(4326)
    value = (
        crs.to_json_dict()
        if crs_type == "projjson"
        else crs.to_wkt(version="WKT2_2019")
        if crs_type == "wkt2:2019"
        else "EPSG:4326"
    )
    declaration = {"crs": value}
    if crs_type is not None:
        declaration["crs_type"] = crs_type
    source = fixtures.arrow_wkb_known_crs()
    field = source.schema.field("geom").with_metadata(
        {
            b"ARROW:extension:name": b"geoarrow.wkb",
            b"ARROW:extension:metadata": json.dumps(declaration).encode(),
        }
    )
    metadata = widget(
        source.cast(source.schema.set(1, field))
    )._get_export_metadata(EmptyArgs())
    assert metadata.geometry_columns == [
        GeometryExportColumn(name="geom", encoding="wkb", crs=value)
    ]
    assert metadata.formats == {
        name: ExportFormatEligibility(available=True)
        for name in ("parquet", "geojson")
    }


@pytest.mark.requires("pyarrow")
def test_arrow_missing_geopandas_reports_required_package(widget: Any) -> None:
    subject = widget(fixtures.arrow_wkb_known_crs())
    with patch.object(DependencyManager.geopandas, "has", return_value=False):
        metadata = subject._get_export_metadata(EmptyArgs())
    assert metadata.formats == {
        name: ExportFormatEligibility(
            available=False,
            reason=f"This Arrow table needs geopandas to export {label}.",
            missing_packages=["geopandas"],
        )
        for name, label in (("parquet", "GeoParquet"), ("geojson", "GeoJSON"))
    }


@pytest.mark.requires("geopandas", "pyarrow")
def test_arrow_geoparquet_checks_writer_version(
    widget: Any,
) -> None:
    subject = widget(fixtures.arrow_wkb_known_crs())
    with patch.object(
        DependencyManager.geopandas, "get_version", return_value="0.14.0"
    ):
        metadata = subject._get_export_metadata(EmptyArgs())
    assert metadata.formats["parquet"] == ExportFormatEligibility(
        available=False,
        reason="Update geopandas to 0.14.1 or newer to export GeoParquet.",
    )


@pytest.mark.requires("geopandas", "pyarrow")
def test_arrow_geoparquet_checks_pyarrow_dependency(widget: Any) -> None:
    subject = widget(fixtures.arrow_wkb_known_crs())
    with patch.object(DependencyManager.pyarrow, "has", return_value=False):
        metadata = subject._get_export_metadata(EmptyArgs())
    assert metadata.formats["parquet"] == ExportFormatEligibility(
        available=False,
        reason="GeoParquet export requires pyarrow.",
        missing_packages=["pyarrow"],
    )


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("choice", ["geom_a", "geom_b"])
def test_arrow_geoparquet_keeps_geometry_crs_and_source(
    widget: Any, choice: str
) -> None:
    import geopandas as gpd
    import pyarrow as pa
    import pyarrow.parquet as pq
    from pyproj import CRS
    from shapely import from_wkt

    source = fixtures.arrow_multi_geometry()
    source = source.append_column(
        "count", pa.array([2**63 + 1, None], type=pa.uint64())
    )
    before = pa.BufferOutputStream()
    with pa.ipc.new_stream(before, source.schema) as writer:
        writer.write_table(source)
    original_bytes = before.getvalue().to_pybytes()

    artifact, filename = _artifact(widget(source), choice)
    reader = pq.ParquetFile(io.BytesIO(artifact))
    file_metadata = reader.metadata.metadata
    assert file_metadata is not None
    geo = json.loads(file_metadata[b"geo"])
    restored = reader.read()
    assert filename.endswith(".parquet")
    assert geo["version"] == "1.0.0"
    assert geo["primary_column"] == choice
    assert set(geo["columns"]) == {"geom_a", "geom_b"}
    for name, crs in (("geom_a", 3857), ("geom_b", 4326)):
        assert geo["columns"][name]["encoding"] == "WKB"
        assert CRS.from_json_dict(
            geo["columns"][name]["crs"]
        ) == CRS.from_epsg(crs)
    assert restored.column_names == source.column_names
    assert restored.to_pylist() == [
        {
            "name": "projected",
            "geom_a": source["geom_a"][0].as_py(),
            "geom_b": from_wkt("POINT (20 5)").wkb,
            "count": 2**63 + 1,
        },
        {"name": "null", "geom_a": None, "geom_b": None, "count": None},
    ]
    frame = gpd.read_parquet(io.BytesIO(artifact))
    assert frame.geometry.name == choice
    assert frame["geom_a"].crs == CRS.from_epsg(3857)
    assert frame["geom_b"].crs == CRS.from_epsg(4326)
    after = pa.BufferOutputStream()
    with pa.ipc.new_stream(after, source.schema) as writer:
        writer.write_table(source)
    assert after.getvalue().to_pybytes() == original_bytes


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize(
    "factory",
    [
        fixtures.arrow_wkb_known_crs,
        fixtures.arrow_wkt,
        fixtures.arrow_wkb_projected,
    ],
)
def test_arrow_geoparquet_sole_geometry_is_default(
    widget: Any, factory: Any
) -> None:
    import geopandas as gpd
    import pyarrow.parquet as pq

    source = factory()
    subject = widget(source)
    metadata = subject._get_export_metadata(EmptyArgs())
    artifact, _ = _artifact(subject)
    file_metadata = pq.read_metadata(io.BytesIO(artifact)).metadata
    assert file_metadata is not None
    geo = json.loads(file_metadata[b"geo"])
    frame = gpd.read_parquet(io.BytesIO(artifact))
    assert geo["primary_column"] == metadata.default_geometry_column
    assert frame.geometry.name == metadata.default_geometry_column
    assert len(frame) == source.num_rows


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize("geometry_only", [False, True])
@pytest.mark.parametrize(
    "factory", [fixtures.arrow_wkb_missing_crs, fixtures.arrow_srid_crs]
)
def test_arrow_geoparquet_unknown_crs_is_explicit(
    widget: Any, factory: Any, empty: bool, geometry_only: bool
) -> None:
    import geopandas as gpd
    import pyarrow.parquet as pq

    source = factory()
    if geometry_only:
        source = source.select(["geom"])
    if empty:
        source = source.slice(0, 0)
    artifact, _ = _artifact(widget(source))
    reader = pq.ParquetFile(io.BytesIO(artifact))
    file_metadata = reader.metadata.metadata
    assert file_metadata is not None
    geo = json.loads(file_metadata[b"geo"])
    frame = gpd.read_parquet(io.BytesIO(artifact))
    assert geo["columns"]["geom"]["crs"] is None
    assert frame.crs is None
    assert reader.read()["geom"].to_pylist() == source["geom"].to_pylist()
    assert reader.metadata.num_rows == source.num_rows
    assert len(frame) == source.num_rows


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize(
    ("factory", "code", "column"),
    [
        (fixtures.arrow_malformed_metadata, "invalid_metadata", "geom"),
        (fixtures.arrow_spherical_edges, "unsupported_representation", "geom"),
        (fixtures.arrow_other_geoarrow, "unsupported_representation", "geom"),
    ],
)
def test_arrow_geoparquet_metadata_rejects_before_conversion(
    widget: Any, factory: Any, code: str, column: str
) -> None:
    import geopandas as gpd

    subject = widget(factory())
    with (
        patch.object(gpd.GeoSeries, "from_wkb") as parse_wkb,
        patch.object(gpd.GeoSeries, "from_wkt") as parse_wkt,
        patch(
            "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
        ) as publish,
    ):
        response = subject._download_as(DownloadAsArgs(format="parquet"))
    assert (
        response.url,
        response.filename,
        response.code,
        response.column,
    ) == (
        "",
        "",
        code,
        column,
    )
    parse_wkb.assert_not_called()
    parse_wkt.assert_not_called()
    publish.assert_not_called()


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b"[]", "invalid_metadata"),
        (b'{"edges":"spherical"}', "unsupported_representation"),
    ],
)
def test_arrow_geoparquet_rejects_secondary_metadata_atomically(
    widget: Any, raw: bytes, code: str
) -> None:
    import geopandas as gpd

    source = fixtures.arrow_multi_geometry()
    field = source.schema.field("geom_b").with_metadata(
        {
            b"ARROW:extension:name": b"geoarrow.wkt",
            b"ARROW:extension:metadata": raw,
        }
    )
    subject = widget(source.cast(source.schema.set(2, field)))
    with (
        patch.object(gpd.GeoSeries, "from_wkb") as parse,
        patch(
            "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
        ) as publish,
    ):
        response = subject._download_as(
            DownloadAsArgs(format="parquet", geometry_column="geom_a")
        )
    assert (
        response.url,
        response.filename,
        response.code,
        response.column,
    ) == ("", "", code, "geom_b")
    parse.assert_not_called()
    publish.assert_not_called()


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("encoding", ["wkb", "wkt"])
def test_arrow_geoparquet_rejects_secondary_m_geometry(
    widget: Any, encoding: str
) -> None:
    import pyarrow as pa
    from shapely import from_wkt

    measured = from_wkt("POINT M (1 2 3)")
    if not getattr(measured, "has_m", False):
        pytest.skip("Installed Shapely cannot represent M coordinates")
    source = fixtures.arrow_multi_geometry()
    field = pa.field(
        "measured",
        pa.binary() if encoding == "wkb" else pa.string(),
        metadata={b"ARROW:extension:name": f"geoarrow.{encoding}".encode()},
    )
    value = measured.wkb if encoding == "wkb" else "POINT M (1 2 3)"
    source = source.append_column(
        field, pa.array([value, None], type=field.type)
    )
    subject = widget(source)
    with patch(
        "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
    ) as publish:
        response = subject._download_as(
            DownloadAsArgs(format="parquet", geometry_column="geom_a")
        )
    assert (
        response.url,
        response.filename,
        response.code,
        response.column,
    ) == ("", "", "unsupported_representation", "measured")
    publish.assert_not_called()


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("encoding", ["wkb", "wkt"])
def test_arrow_geoparquet_invalid_geometry_publishes_no_artifact(
    widget: Any, encoding: str
) -> None:
    import pyarrow as pa

    source = fixtures.arrow_invalid_wkb()
    if encoding == "wkt":
        source = fixtures.arrow_wkt()
        source = source.set_column(
            1, source.schema.field("geom"), pa.array(["invalid", None, None])
        )
    subject = widget(source)
    with patch(
        "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
    ) as publish:
        response = subject._download_as(DownloadAsArgs(format="parquet"))
    assert (response.url, response.filename, response.code) == (
        "",
        "",
        "conversion_failed",
    )
    publish.assert_not_called()


@pytest.mark.requires("geopandas", "pyarrow")
def test_arrow_geoparquet_ambiguous_geometry_requires_choice(
    widget: Any,
) -> None:
    subject = widget(fixtures.arrow_multi_geometry())
    response = subject._download_as(DownloadAsArgs(format="parquet"))
    assert (response.url, response.filename, response.code) == (
        "",
        "",
        "geometry_required",
    )


@pytest.mark.requires("geopandas", "pyarrow")
def test_arrow_geoparquet_exports_only_selected_rows() -> None:
    import pyarrow.parquet as pq

    source = fixtures.arrow_multi_geometry()
    subject = ui.table(source, selection="multi")
    subject._convert_value(["1"])
    artifact, _ = _artifact(subject, "geom_b")
    restored = pq.read_table(io.BytesIO(artifact))
    assert restored.to_pylist() == [
        {"name": "null", "geom_a": None, "geom_b": None}
    ]


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("encoding", ["wkb", "wkt"])
def test_arrow_geoparquet_registered_extension_storage(
    widget: Any, encoding: Literal["wkb", "wkt"]
) -> None:
    import geopandas as gpd
    import pyarrow as pa
    import pyarrow.parquet as pq

    name = f"geoarrow.{encoding}"
    storage_type = pa.binary() if encoding == "wkb" else pa.string()

    class GeometryType(pa.ExtensionType):
        def __init__(self) -> None:
            super().__init__(storage_type, name)

        def __arrow_ext_serialize__(self) -> bytes:
            return b'{"crs":"EPSG:4326"}'

        @classmethod
        def __arrow_ext_deserialize__(
            cls, _storage_type: Any, _serialized: bytes
        ) -> Any:
            return cls()

    extension = GeometryType()
    pa.register_extension_type(extension)  # type: ignore[arg-type]
    try:
        value = fixtures.WKB_POINT_1_2 if encoding == "wkb" else "POINT (1 2)"
        chunks = [
            pa.ExtensionArray.from_storage(
                extension, pa.array([value], type=storage_type)
            ),
            pa.ExtensionArray.from_storage(
                extension, pa.array([None], type=storage_type)
            ),
        ]
        source = pa.Table.from_arrays(
            [pa.array(["point", "null"]), pa.chunked_array(chunks)],
            names=["name", "geom"],
        )
        subject = widget(source)
        metadata = subject._get_export_metadata(EmptyArgs())
        assert metadata.geometry_columns == [
            GeometryExportColumn("geom", encoding, "EPSG:4326")
        ]
        artifact, _ = _artifact(subject)
        assert pq.read_table(io.BytesIO(artifact))["geom"].to_pylist() == [
            fixtures.WKB_POINT_1_2,
            None,
        ]
        frame = gpd.read_parquet(io.BytesIO(artifact))
        assert frame.geometry.name == "geom"
        assert frame.crs.to_epsg() == 4326
        assert source["geom"].num_chunks == 2
        assert source["geom"].to_pylist() == [value, None]
    finally:
        pa.unregister_extension_type(name)


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("missing", ["geopandas", "pyarrow", "version"])
def test_arrow_geoparquet_rechecks_dependencies_before_conversion(
    widget: Any, missing: str
) -> None:
    import geopandas as gpd

    subject = widget(fixtures.arrow_wkb_known_crs())
    dependency = (
        DependencyManager.pyarrow
        if missing == "pyarrow"
        else DependencyManager.geopandas
    )
    method = "has_at_version" if missing == "version" else "has"
    with (
        patch.object(dependency, method, return_value=False),
        patch.object(gpd.GeoSeries, "from_wkb") as parse,
        patch(
            "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
        ) as publish,
    ):
        response = subject._download_as(DownloadAsArgs(format="parquet"))
    assert (
        response.url,
        response.filename,
        response.code,
        response.missing_packages,
    ) == (
        "",
        "",
        "unsupported_version" if missing == "version" else "missing_packages",
        None if missing == "version" else [missing],
    )
    parse.assert_not_called()
    publish.assert_not_called()


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

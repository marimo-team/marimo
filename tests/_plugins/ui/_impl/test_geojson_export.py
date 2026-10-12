# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import Any, Literal
from unittest.mock import patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.table import DownloadAsArgs, DownloadGeoJSONArgs
from marimo._plugins.ui._impl.tables.geometry_export import (
    ExportFormatEligibility,
)
from marimo._runtime.functions import EmptyArgs
from marimo._utils.data_uri import from_data_uri
from tests._plugins.ui._impl.tables import geometry_fixtures as fixtures

pytestmark = pytest.mark.requires("geopandas")


@pytest.mark.parametrize("wrapped", [False, True], ids=["native", "narwhals"])
@pytest.mark.parametrize("geometry_only", [False, True])
@pytest.mark.parametrize("index_kind", ["range", "named", "unnamed", "multi"])
def test_properties_follow_manager_index_policy(
    widget: Any, wrapped: bool, geometry_only: bool, index_kind: str
) -> None:
    import narwhals.stable.v2 as nw
    import pandas as pd

    source = _source().drop(columns=["alternate"])
    if geometry_only:
        source = source[["location"]]
    if index_kind == "named":
        source.index = pd.Index([7, 7], name="source_row")
    elif index_kind == "unnamed":
        source.index = pd.Index([7, 7])
    elif index_kind == "multi":
        source.index = pd.MultiIndex.from_tuples(
            [("a", 7), ("a", 7)], names=["group", "row"]
        )
    subject = widget(
        nw.from_native(source) if wrapped else source,
        **({"selection": None} if widget is ui.table else {}),
    )
    ordinary = subject._download_as(DownloadAsArgs(format="json"))
    expected = json.loads(from_data_uri(ordinary.url)[1])
    for row in expected:
        del row["location"]
    assert [
        feature["properties"] for feature in _artifact(subject)["features"]
    ] == expected


def test_old_shapely_rejects_direct_geojson_before_publication(
    widget: Any,
) -> None:
    import geopandas as gpd

    subject = widget(_source())
    export_function = next(
        function
        for function in subject._args.functions
        if function.name == "download_geojson"
    )
    with (
        patch.object(
            DependencyManager.shapely, "has_at_version", return_value=False
        ),
        patch.object(gpd.GeoSeries, "to_crs") as reproject,
        patch(
            "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
        ) as publish,
    ):
        response = export_function({"format": "geojson"})
    assert response.code == "unsupported_version"
    assert "shapely" in response.error
    assert "2.0" in response.error
    assert (response.url, response.filename, response.missing_packages) == (
        "",
        "",
        None,
    )
    reproject.assert_not_called()
    publish.assert_not_called()


@pytest.mark.parametrize("ensure_ascii", [False, True])
@pytest.mark.parametrize("choice", [None, "alternate"])
def test_registered_geojson_keeps_geometry_and_ascii_options(
    widget: Any, ensure_ascii: bool, choice: str | None
) -> None:
    source = _source()
    source["name"] = ["café", "null"]
    subject = widget(source)
    export_function = next(
        function
        for function in subject._args.functions
        if function.name == "download_geojson"
    )
    response = export_function(
        {
            "format": "geojson",
            "geometry_column": choice,
            "options": {"ensure_ascii": ensure_ascii},
        }
    )
    assert response.error is None
    assert response.filename.endswith(".geojson")
    text = from_data_uri(response.url)[1].decode("utf-8")
    assert (r"\u00e9" in text) is ensure_ascii
    feature = json.loads(text)["features"][0]
    assert feature["properties"]["name"] == "café"
    assert feature["geometry"]["coordinates"] == pytest.approx(
        [20, 5] if choice == "alternate" else [10, 0]
    )


@pytest.fixture(params=[ui.table, ui.dataframe], ids=["table", "dataframe"])
def widget(request: pytest.FixtureRequest) -> Any:
    return request.param


def _reject_constant(value: str) -> Any:
    raise ValueError(value)


def _artifact(subject: Any, choice: str | None = None) -> dict[str, Any]:
    export_function = next(
        function
        for function in subject._args.functions
        if function.name == "download_geojson"
    )
    response = export_function(
        {"format": "geojson", "geometry_column": choice}
    )
    assert response.error is None, response.error
    assert response.filename.endswith(".geojson")
    document = json.loads(
        from_data_uri(response.url)[1], parse_constant=_reject_constant
    )
    assert isinstance(document, dict)
    return document


def _source() -> Any:
    import geopandas as gpd
    from shapely.geometry import Point

    return gpd.GeoDataFrame(
        {
            "name": ["projected", "null"],
            "location": gpd.GeoSeries(
                [Point(1113194.9079327357, 0), None], crs="EPSG:3857"
            ),
            "alternate": gpd.GeoSeries([Point(20, 5), None], crs="EPSG:4326"),
        },
        geometry="location",
    )


@pytest.mark.parametrize("choice", [None, "alternate"])
def test_reprojection_and_secondary_wkt_preserve_source(
    widget: Any, choice: str | None
) -> None:
    source = _source()
    original = source.copy(deep=True)
    subject = widget(source)
    with patch.object(DependencyManager.pyarrow, "has", return_value=False):
        document = _artifact(subject, choice)
    assert document == {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": pytest.approx(
                        [20, 5] if choice else [10, 0]
                    ),
                },
                "properties": {
                    "name": "projected",
                    ("location" if choice else "alternate"): (
                        "POINT (1113194.9079327357 0)"
                        if choice
                        else "POINT (20 5)"
                    ),
                },
            },
            {
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "name": "null",
                    ("location" if choice else "alternate"): None,
                },
            },
        ],
    }
    assert source.equals(original)
    assert source.geometry.name == "location"
    assert source.crs == original.crs
    assert source["alternate"].crs == original["alternate"].crs


@pytest.mark.parametrize("empty", [False, True])
def test_null_and_empty_tables_require_crs(widget: Any, empty: bool) -> None:
    source = fixtures.gdf_all_null()
    if empty:
        source = source.head(0)
    subject = widget(source)
    with patch(
        "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
    ) as publish:
        response = subject._download_geojson(
            DownloadGeoJSONArgs(format="geojson")
        )
    assert (
        response.url,
        response.filename,
        response.code,
        response.column,
    ) == ("", "", "missing_crs", "geometry")
    publish.assert_not_called()


@pytest.mark.parametrize("empty", [False, True])
def test_null_and_empty_tables_with_crs(widget: Any, empty: bool) -> None:
    source = fixtures.gdf_all_null().set_crs("EPSG:4326")
    if empty:
        source = source.head(0)
    assert _artifact(widget(source)) == {
        "type": "FeatureCollection",
        "features": []
        if empty
        else [
            {"type": "Feature", "geometry": None, "properties": {"name": name}}
            for name in ["a", "b"]
        ],
    }


def test_geometry_only_table_keeps_rows(widget: Any) -> None:
    source = _source()[["location"]]
    assert [
        feature["properties"]
        for feature in _artifact(widget(source))["features"]
    ] == [{}, {}]


def test_geometry_only_table_keeps_named_index_properties(widget: Any) -> None:
    import pandas as pd

    source = _source()[["location"]]
    source.index = pd.Index([7, 7], name="source_row")
    assert [
        feature["properties"]
        for feature in _artifact(widget(source))["features"]
    ] == [{"source_row": 7}, {"source_row": 7}]


def test_projected_z_coordinate_is_preserved(widget: Any) -> None:
    import geopandas as gpd
    from shapely.geometry import Point

    source = gpd.GeoDataFrame(
        geometry=[Point(1113194.9079327357, 0, 123)], crs="EPSG:3857"
    )
    assert _artifact(widget(source))["features"][0]["geometry"][
        "coordinates"
    ] == pytest.approx([10, 0, 123])


def test_duplicate_indices_and_reserved_property_names(widget: Any) -> None:
    source = _source().rename(columns={"alternate": "geometry"})
    source["id"] = ["first", "second"]
    source["properties"] = [{"a": 1}, None]
    source.index = [7, 7]
    features = _artifact(widget(source))["features"]
    assert [feature["properties"] for feature in features] == [
        {
            "Index0": 7,
            "name": "projected",
            "geometry": "POINT (20 5)",
            "id": "first",
            "properties": {"a": 1},
        },
        {
            "Index0": 7,
            "name": "null",
            "geometry": None,
            "id": "second",
            "properties": None,
        },
    ]
    assert features[0]["geometry"]["coordinates"] == pytest.approx([10, 0])
    assert features[1]["geometry"] is None
    assert all("id" not in feature for feature in features)


def test_unnamed_geometry_can_be_chosen(widget: Any) -> None:
    source = _source().rename(columns={"alternate": ""})
    assert _artifact(widget(source), "")["features"][0]["geometry"] == {
        "type": "Point",
        "coordinates": [20, 5],
    }


@pytest.mark.parametrize(
    "factory", [fixtures.gdf_stale_pointer, fixtures.gdf_no_active_geometry]
)
def test_sole_geometry_resolves_without_active_primary(
    widget: Any, factory: Any
) -> None:
    source = factory()
    column = "geom" if factory is fixtures.gdf_stale_pointer else "g"
    source[column] = source[column].set_crs("EPSG:4326", allow_override=True)
    assert len(_artifact(widget(source))["features"]) == len(source)


def test_ambiguous_geometry_requires_choice(widget: Any) -> None:
    import pandas as pd

    subject = widget(pd.DataFrame(_source()))
    with patch(
        "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
    ) as publish:
        response = subject._download_geojson(
            DownloadGeoJSONArgs(format="geojson")
        )
    assert (response.url, response.code) == ("", "geometry_required")
    publish.assert_not_called()
    assert _artifact(subject, "alternate")["features"][0]["geometry"][
        "coordinates"
    ] == [20, 5]


def test_known_alternate_crs_can_override_missing_primary_crs(
    widget: Any,
) -> None:
    import geopandas as gpd

    known = _source()
    source = gpd.GeoDataFrame(
        {
            "location": gpd.GeoSeries(list(known["location"])),
            "alternate": known["alternate"],
        },
        geometry="location",
    )
    subject = widget(source)
    assert (
        subject._download_geojson(DownloadGeoJSONArgs(format="geojson")).code
        == "missing_crs"
    )
    assert _artifact(subject, "alternate")["features"][0]["geometry"][
        "coordinates"
    ] == [20, 5]
    assert source["location"].crs is None


def test_properties_match_ordinary_json_policy(widget: Any) -> None:
    import datetime

    import pandas as pd

    class CustomValue:
        def __str__(self) -> str:
            return "custom-value"

    source = _source()
    source["date"] = [datetime.date(2026, 10, 5), None]
    source["timestamp"] = [pd.Timestamp("2026-10-05T13:00:00Z"), None]
    source["duration"] = [pd.Timedelta(days=1), None]
    source["custom"] = [CustomValue(), None]
    source["bytes"] = [b"abc", None]
    source["complex"] = [1 + 2j, None]
    source["number"] = [float("inf"), float("nan")]
    source["nested"] = [{"n": float("nan")}, None]
    source["large"] = [2**60, 2**60 + 1]
    subject = widget(source)
    response = subject._download_as(DownloadAsArgs(format="json"))
    ordinary = json.loads(
        from_data_uri(response.url)[1], parse_constant=_reject_constant
    )
    expected = [
        {key: value for key, value in row.items() if key != "location"}
        for row in ordinary
    ]
    assert [
        feature["properties"] for feature in _artifact(subject)["features"]
    ] == expected


def test_secondary_wkt_is_complete_and_can_retain_m(widget: Any) -> None:
    import geopandas as gpd
    import numpy as np
    from shapely import from_wkt
    from shapely.geometry import LineString

    source = _source()
    long_geometry = LineString([(i, i / 7) for i in range(4000)])
    source["long"] = gpd.GeoSeries([long_geometry, None], crs="EPSG:3857")
    measured = from_wkt("POINT M (1 2 3)")
    if getattr(measured, "has_m", False):
        source["measured"] = gpd.GeoSeries([measured, None], crs="EPSG:4326")
    properties = _artifact(widget(source))["features"][0]["properties"]
    assert len(properties["long"]) > 40_000
    assert np.asarray(from_wkt(properties["long"]).coords) == pytest.approx(
        np.asarray(long_geometry.coords), rel=1e-15, abs=0
    )
    if "measured" in properties:
        assert from_wkt(properties["measured"]).wkb == measured.wkb


@pytest.mark.parametrize(
    "geometry_wkt",
    [
        "POINT Z (10 20 30)",
        "LINESTRING Z (0 0 1, 1 1 2)",
        "POLYGON ((0 0, 0 4, 4 4, 4 0, 0 0), (1 1, 3 1, 3 3, 1 3, 1 1))",
        "MULTIPOLYGON (((0 0, 0 4, 4 4, 4 0, 0 0)))",
        "GEOMETRYCOLLECTION (POINT Z (1 2 3), MULTIPOLYGON (((0 0, 0 4, 4 4, 4 0, 0 0))))",
        "MULTIPOINT ((1 2), (3 4))",
        "MULTILINESTRING ((1 2, 3 4), (5 6, 7 8))",
    ],
)
def test_supported_geometries_and_ring_orientation(
    widget: Any, geometry_wkt: str
) -> None:
    import geopandas as gpd
    from shapely import from_wkt
    from shapely.geometry import shape

    geometry = from_wkt(geometry_wkt)
    source = gpd.GeoDataFrame(geometry=[geometry], crs="EPSG:4326")
    result = _artifact(widget(source))["features"][0]["geometry"]
    restored = shape(result)
    assert restored.equals(geometry)
    assert restored.has_z == geometry.has_z
    assert source.geometry.iloc[0].wkb == geometry.wkb

    def check_rings(value: Any) -> None:
        if value.geom_type == "Polygon":
            assert value.exterior.is_ccw
            assert all(not ring.is_ccw for ring in value.interiors)
        elif hasattr(value, "geoms"):
            for child in value.geoms:
                check_rings(child)

    check_rings(restored)
    if geometry.geom_type == "Point":
        assert result["coordinates"] == [10, 20, 30]


@pytest.mark.parametrize(
    "geometry_type",
    [
        "POINT",
        "LINESTRING",
        "POLYGON",
        "MULTIPOINT",
        "MULTILINESTRING",
        "MULTIPOLYGON",
        "GEOMETRYCOLLECTION",
    ],
)
def test_empty_geometry_preserves_its_type(
    widget: Any, geometry_type: str
) -> None:
    import geopandas as gpd
    from shapely import from_wkt

    source = gpd.GeoDataFrame(
        geometry=[from_wkt(f"{geometry_type} EMPTY")], crs="EPSG:4326"
    )
    result = _artifact(widget(source))["features"][0]["geometry"]
    assert result == {
        "type": source.geometry.iloc[0].geom_type,
        "geometries"
        if geometry_type == "GEOMETRYCOLLECTION"
        else "coordinates": [],
    }


@pytest.mark.parametrize(
    "geometry_wkt",
    [
        "POINT M (1 2 3)",
        "POINT ZM (1 2 3 4)",
        "GEOMETRYCOLLECTION (POINT M (1 2 3))",
    ],
)
def test_selected_m_geometry_is_rejected_atomically(
    widget: Any, geometry_wkt: str
) -> None:
    import geopandas as gpd
    from shapely import from_wkt

    geometry = from_wkt(geometry_wkt)
    if not getattr(geometry, "has_m", False):
        pytest.skip("Installed Shapely cannot represent M coordinates")
    subject = widget(gpd.GeoDataFrame(geometry=[geometry], crs="EPSG:4326"))
    with patch(
        "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
    ) as publish:
        response = subject._download_geojson(
            DownloadGeoJSONArgs(format="geojson")
        )
    assert (response.url, response.code, response.column) == (
        "",
        "unsupported_representation",
        "geometry",
    )
    publish.assert_not_called()


@pytest.mark.parametrize(
    ("geometry_wkt", "crs"),
    [
        ("POINT (Infinity 2)", "EPSG:4326"),
        ("LINESTRING (0 0, NaN 2)", "EPSG:4326"),
        ("POINT Z (1 2 Infinity)", "EPSG:4326"),
        ("POINT Z (1 2 NaN)", "EPSG:4326"),
        ("POINT (190 20)", "EPSG:4326"),
        ("POINT (1 95)", "EPSG:4326"),
        ("POINT (30000000 0)", "EPSG:3857"),
        ("POINT (1 1e300)", "EPSG:3857"),
    ],
)
def test_invalid_or_lossy_coordinates_publish_no_artifact(
    widget: Any, geometry_wkt: str, crs: str
) -> None:
    import geopandas as gpd
    from shapely import from_wkt

    subject = widget(
        gpd.GeoDataFrame(geometry=[from_wkt(geometry_wkt)], crs=crs)
    )
    with patch(
        "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
    ) as publish:
        response = subject._download_geojson(
            DownloadGeoJSONArgs(format="geojson")
        )
    assert (response.url, response.filename, response.code) == (
        "",
        "",
        "conversion_failed",
    )
    publish.assert_not_called()


@pytest.mark.parametrize(
    "invalid_json",
    [
        '[{"name":NaN,"alternate":"POINT (20 5)"},{"name":"null","alternate":null}]',
        '[{"name":Infinity,"alternate":"POINT (20 5)"},{"name":"null","alternate":null}]',
        '[{"name":1e400,"alternate":"POINT (20 5)"},{"name":"null","alternate":null}]',
        '[{"name":"projected"},{"name":"null"}]',
        "[]",
        "{}",
    ],
)
def test_invalid_property_conversion_publishes_no_artifact(
    widget: Any, invalid_json: str
) -> None:
    subject = widget(_source())
    import pandas as pd

    from marimo._plugins.ui._impl.tables.utils import get_table_manager

    manager_type = type(get_table_manager(pd.DataFrame({"value": [1]})))
    with (
        patch.object(manager_type, "to_json_str", return_value=invalid_json),
        patch(
            "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
        ) as publish,
    ):
        response = subject._download_geojson(
            DownloadGeoJSONArgs(format="geojson")
        )
    assert (response.url, response.filename, response.code) == (
        "",
        "",
        "conversion_failed",
    )
    publish.assert_not_called()


def test_truncated_secondary_wkt_publishes_no_artifact(widget: Any) -> None:
    import geopandas as gpd
    import pandas as pd

    subject = widget(_source())
    with (
        patch.object(
            gpd.GeoSeries,
            "to_wkt",
            return_value=pd.Series(["POINT (21 5)", None]),
        ),
        patch(
            "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
        ) as publish,
    ):
        response = subject._download_geojson(
            DownloadGeoJSONArgs(format="geojson")
        )
    assert (response.url, response.code) == ("", "conversion_failed")
    publish.assert_not_called()


@pytest.mark.parametrize(
    "failure", ["exception", "id", "crs", "geometry", "missing_row"]
)
def test_invalid_feature_writer_publishes_no_artifact(
    widget: Any, failure: str
) -> None:
    import geopandas as gpd

    subject = widget(_source())
    original = gpd.GeoDataFrame.iterfeatures

    def broken_writer(frame: Any, **kwargs: Any) -> Any:
        if failure == "exception":
            raise ValueError("writer failed")
        for index, feature in enumerate(original(frame, **kwargs)):
            if failure == "missing_row" and index == 0:
                continue
            if failure in ("id", "crs"):
                feature[failure] = "unexpected"
            elif failure == "geometry":
                feature["geometry"] = None
            yield feature

    with (
        patch.object(gpd.GeoDataFrame, "iterfeatures", broken_writer),
        patch(
            "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
        ) as publish,
    ):
        response = subject._download_geojson(
            DownloadGeoJSONArgs(format="geojson")
        )
    assert (response.url, response.filename, response.code) == (
        "",
        "",
        "conversion_failed",
    )
    publish.assert_not_called()


def test_missing_geopandas_is_rechecked(widget: Any) -> None:
    subject = widget(_source())
    with (
        patch.object(DependencyManager.geopandas, "has", return_value=False),
        patch(
            "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
        ) as publish,
    ):
        response = subject._download_geojson(
            DownloadGeoJSONArgs(format="geojson")
        )
    assert (response.url, response.code, response.missing_packages) == (
        "",
        "missing_packages",
        ["geopandas"],
    )
    publish.assert_not_called()


@pytest.mark.parametrize("choice", ["absent", "name"])
def test_invalid_choice_is_rejected_atomically(
    widget: Any, choice: str
) -> None:
    subject = widget(_source())
    with patch(
        "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
    ) as publish:
        response = subject._download_geojson(
            DownloadGeoJSONArgs(format="geojson", geometry_column=choice)
        )
    assert (response.url, response.code, response.column) == (
        "",
        "invalid_geometry",
        choice,
    )
    publish.assert_not_called()


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize(
    "factory",
    [
        fixtures.arrow_wkb_known_crs,
        fixtures.arrow_wkt,
        fixtures.arrow_multi_geometry,
    ],
)
def test_arrow_geometry_is_eligible_for_geojson(
    widget: Any, factory: Any
) -> None:
    metadata = widget(factory())._get_export_metadata(EmptyArgs())
    assert metadata.formats["geojson"] == ExportFormatEligibility(
        available=True
    )


@pytest.mark.requires("geopandas", "pyarrow")
def test_arrow_geojson_checks_shapely_version(widget: Any) -> None:
    subject = widget(fixtures.arrow_wkb_known_crs())
    with patch.object(
        DependencyManager.shapely, "has_at_version", return_value=False
    ):
        metadata = subject._get_export_metadata(EmptyArgs())
    assert metadata.formats["geojson"] == ExportFormatEligibility(
        available=False,
        reason="Update shapely to 2.0 or newer to export GeoJSON.",
    )


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("choice", ["geom_a", "geom_b"])
@pytest.mark.parametrize("wrapped", [False, True], ids=["native", "narwhals"])
def test_arrow_geojson_reprojects_and_preserves_source_properties(
    widget: Any, choice: str, wrapped: bool
) -> None:
    import datetime

    import narwhals.stable.v2 as nw
    import pyarrow as pa
    from shapely import from_wkt

    source = fixtures.arrow_multi_geometry()
    source = source.append_column(
        "count", pa.array([2**63 + 1, None], type=pa.uint64())
    )
    source = source.append_column("float", pa.array([1.25, None]))
    source = source.append_column(
        "date", pa.array([datetime.date(2026, 10, 5), None])
    )
    source = source.append_column(
        "nested", pa.array([{"items": [1, 2]}, None])
    )
    subject = widget(nw.from_native(source) if wrapped else source)
    before = pa.BufferOutputStream()
    with pa.ipc.new_stream(before, source.schema) as writer:
        writer.write_table(source)
    original_bytes = before.getvalue().to_pybytes()
    ordinary = subject._download_as(DownloadAsArgs(format="json"))
    assert ordinary.error is None
    expected = json.loads(
        from_data_uri(ordinary.url)[1], parse_constant=_reject_constant
    )
    for row in expected:
        del row[choice]

    document = _artifact(subject, choice)
    assert document["type"] == "FeatureCollection"
    assert [
        feature["properties"] for feature in document["features"]
    ] == expected
    assert document["features"][0]["geometry"] == {
        "type": "Point",
        "coordinates": pytest.approx(
            [10, 0] if choice == "geom_a" else [20, 5]
        ),
    }
    assert document["features"][1]["geometry"] is None
    secondary = "geom_b" if choice == "geom_a" else "geom_a"
    text = document["features"][0]["properties"][secondary]
    restored = from_wkt(text)
    expected_coordinates: list[float] = (
        [20, 5] if choice == "geom_a" else [1113194.9079327357, 0]
    )
    assert next(iter(restored.coords)) == pytest.approx(expected_coordinates)
    assert document["features"][1]["properties"][secondary] is None
    after = pa.BufferOutputStream()
    with pa.ipc.new_stream(after, source.schema) as writer:
        writer.write_table(source)
    assert after.getvalue().to_pybytes() == original_bytes


@pytest.mark.requires("geopandas", "pyarrow")
def test_arrow_geojson_projected_wkb_uses_sole_geometry(widget: Any) -> None:
    document = _artifact(widget(fixtures.arrow_wkb_projected()))
    assert document == {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": pytest.approx([10, 0]),
                },
                "properties": {"name": "projected"},
            },
            {
                "type": "Feature",
                "geometry": None,
                "properties": {"name": "null"},
            },
        ],
    }


@pytest.mark.requires("geopandas", "pyarrow")
def test_arrow_geojson_nonfinite_properties_publish_no_artifact(
    widget: Any,
) -> None:
    import pyarrow as pa

    source = fixtures.arrow_wkb_projected().append_column(
        "value", pa.array([float("nan"), None])
    )
    subject = widget(source)
    function = next(
        function
        for function in subject._args.functions
        if function.name == "download_geojson"
    )
    with patch(
        "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
    ) as publish:
        response = function({"format": "geojson"})
    assert (response.url, response.filename, response.code) == (
        "",
        "",
        "conversion_failed",
    )
    publish.assert_not_called()


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("encoding", ["wkb", "wkt"])
def test_arrow_geojson_secondary_wkt_is_complete(
    widget: Any, encoding: str
) -> None:
    import numpy as np
    import pyarrow as pa
    from shapely import from_wkt
    from shapely.geometry import LineString

    geometry = LineString([(i, i / 7) for i in range(4000)])
    value = geometry.wkb if encoding == "wkb" else geometry.wkt
    source = fixtures.arrow_wkb_projected()
    field = pa.field(
        "secondary",
        pa.binary() if encoding == "wkb" else pa.string(),
        metadata={b"ARROW:extension:name": f"geoarrow.{encoding}".encode()},
    )
    source = source.append_column(
        field, pa.array([value, None], type=field.type)
    )
    properties = _artifact(widget(source), "geom_a")["features"][0][
        "properties"
    ]
    assert len(properties["secondary"]) > 40_000
    assert np.asarray(
        from_wkt(properties["secondary"]).coords
    ) == pytest.approx(np.asarray(geometry.coords), rel=1e-15, abs=0)


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("srid", [False, True])
def test_arrow_geojson_known_alternate_crs_can_be_chosen(
    widget: Any, srid: bool
) -> None:
    source = fixtures.arrow_multi_geometry()
    raw = b'{"crs":"local-id","crs_type":"srid"}' if srid else b"{}"
    field = source.schema.field("geom_a").with_metadata(
        {
            b"ARROW:extension:name": b"geoarrow.wkb",
            b"ARROW:extension:metadata": raw,
        }
    )
    subject = widget(source.cast(source.schema.set(1, field)))
    function = next(
        function
        for function in subject._args.functions
        if function.name == "download_geojson"
    )
    response = function({"format": "geojson", "geometry_column": "geom_a"})
    assert (response.url, response.code, response.column) == (
        "",
        "missing_crs",
        "geom_a",
    )
    features = _artifact(subject, "geom_b")["features"]
    assert features[0]["geometry"]["coordinates"] == [20, 5]
    assert (
        features[0]["properties"]["geom_a"] == "POINT (1113194.9079327357 0)"
    )


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("empty", [False, True])
def test_arrow_geojson_geometry_only_keeps_rows_and_z(
    widget: Any, empty: bool
) -> None:
    source = fixtures.arrow_wkt().select(["geom"])
    if empty:
        source = source.slice(0, 0)
    expected = (
        []
        if empty
        else [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1, 2]},
                "properties": {},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1, 2, 3]},
                "properties": {},
            },
            {"type": "Feature", "geometry": None, "properties": {}},
        ]
    )
    assert _artifact(widget(source)) == {
        "type": "FeatureCollection",
        "features": expected,
    }


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize(
    "factory", [fixtures.arrow_wkb_missing_crs, fixtures.arrow_srid_crs]
)
def test_arrow_geojson_unknown_crs_rejects_before_reprojection(
    widget: Any, factory: Any, empty: bool
) -> None:
    import geopandas as gpd

    source = factory()
    if empty:
        source = source.slice(0, 0)
    subject = widget(source)
    function = next(
        function
        for function in subject._args.functions
        if function.name == "download_geojson"
    )
    with (
        patch.object(gpd.GeoSeries, "to_crs") as reproject,
        patch(
            "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
        ) as publish,
    ):
        response = function({"format": "geojson"})
    assert (
        response.url,
        response.filename,
        response.code,
        response.column,
    ) == ("", "", "missing_crs", "geom")
    assert (
        response.error
        == "Geometry column 'geom' needs a CRS for GeoJSON export. Declare its source CRS in Python before exporting."
    )
    reproject.assert_not_called()
    publish.assert_not_called()


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize(
    ("factory", "code"),
    [
        (fixtures.arrow_malformed_metadata, "invalid_metadata"),
        (fixtures.arrow_spherical_edges, "unsupported_representation"),
        (fixtures.arrow_other_geoarrow, "unsupported_representation"),
        (fixtures.arrow_invalid_wkb, "conversion_failed"),
    ],
)
def test_arrow_geojson_failures_publish_no_artifact(
    widget: Any, factory: Any, code: str
) -> None:
    subject = widget(factory())
    function = next(
        function
        for function in subject._args.functions
        if function.name == "download_geojson"
    )
    with patch(
        "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
    ) as publish:
        response = function({"format": "geojson"})
    assert (response.url, response.filename, response.code) == ("", "", code)
    publish.assert_not_called()


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("choice", [None, "name", "missing"])
def test_arrow_geojson_requires_valid_geometry_choice(
    widget: Any, choice: str | None
) -> None:
    subject = widget(fixtures.arrow_multi_geometry())
    function = next(
        function
        for function in subject._args.functions
        if function.name == "download_geojson"
    )
    with patch(
        "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
    ) as publish:
        response = function({"format": "geojson", "geometry_column": choice})
    assert (response.url, response.filename, response.code) == (
        "",
        "",
        "geometry_required" if choice is None else "invalid_geometry",
    )
    publish.assert_not_called()


@pytest.mark.requires("geopandas", "pyarrow")
def test_arrow_geojson_selected_table_rows_only() -> None:
    subject = ui.table(fixtures.arrow_multi_geometry(), selection="multi")
    subject._convert_value(["1"])
    assert _artifact(subject, "geom_a") == {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": None,
                "properties": {"name": "null", "geom_b": None},
            }
        ],
    }


@pytest.mark.requires("geopandas", "pyarrow")
def test_arrow_geojson_uses_transformed_dataframe_value() -> None:
    import pyarrow as pa

    subject = ui.dataframe(fixtures.arrow_multi_geometry())
    subject._update(
        {
            "transforms": [
                {"type": "select_columns", "column_ids": ["name", "geom_b"]}
            ]
        }
    )
    assert _artifact(subject) == {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [20, 5]},
                "properties": {"name": "projected"},
            },
            {
                "type": "Feature",
                "geometry": None,
                "properties": {"name": "null"},
            },
        ],
    }
    transformed = subject._value
    assert isinstance(transformed, pa.Table)
    subject._value = transformed.slice(1, 1)
    assert len(_artifact(subject)["features"]) == 1
    response = subject._download_geojson(
        DownloadGeoJSONArgs(format="geojson", geometry_column="geom_a")
    )
    assert (response.url, response.code, response.column) == (
        "",
        "invalid_geometry",
        "geom_a",
    )


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("encoding", ["wkb", "wkt"])
@pytest.mark.parametrize("choice", ["geom_a", "registered"])
def test_arrow_geojson_registered_primary_and_secondary_geometry(
    widget: Any, encoding: Literal["wkb", "wkt"], choice: str
) -> None:
    import pyarrow as pa
    from shapely import from_wkt

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
        values = pa.ExtensionArray.from_storage(
            extension, pa.array([value, None], type=storage_type)
        )
        source = fixtures.arrow_multi_geometry().append_column(
            "registered", values
        )
        subject = widget(source)
        features = _artifact(subject, choice)["features"]
        assert features[0]["geometry"]["coordinates"] == pytest.approx(
            [10, 0] if choice == "geom_a" else [1, 2]
        )
        secondary = "registered" if choice == "geom_a" else "geom_a"
        assert next(
            iter(from_wkt(features[0]["properties"][secondary]).coords)
        ) == pytest.approx(
            [1, 2] if choice == "geom_a" else [1113194.9079327357, 0]
        )
        assert features[1]["geometry"] is None
        assert features[1]["properties"][secondary] is None
        assert source["registered"].to_pylist() == [value, None]
    finally:
        pa.unregister_extension_type(name)


@pytest.mark.requires("geopandas", "pyarrow")
@pytest.mark.parametrize("missing", ["geopandas", "shapely"])
def test_arrow_geojson_rechecks_dependencies_before_conversion(
    widget: Any, missing: str
) -> None:
    import geopandas as gpd

    subject = widget(fixtures.arrow_wkb_projected())
    function = next(
        function
        for function in subject._args.functions
        if function.name == "download_geojson"
    )
    dependency = (
        DependencyManager.geopandas
        if missing == "geopandas"
        else DependencyManager.shapely
    )
    method = "has" if missing == "geopandas" else "has_at_version"
    with (
        patch.object(dependency, method, return_value=False),
        patch.object(gpd.GeoSeries, "from_wkb") as parse,
        patch(
            "marimo._plugins.ui._impl.utils.dataframe.mo_data.any_data"
        ) as publish,
    ):
        response = function({"format": "geojson"})
    assert (
        response.url,
        response.filename,
        response.code,
        response.missing_packages,
    ) == (
        "",
        "",
        "missing_packages"
        if missing == "geopandas"
        else "unsupported_version",
        ["geopandas"] if missing == "geopandas" else None,
    )
    parse.assert_not_called()
    publish.assert_not_called()


def test_table_selection_search_and_cell_scope() -> None:
    from marimo._plugins.ui._impl.table import SearchTableArgs

    source = _source()
    subject = ui.table(source, selection="multi")
    subject._convert_value(["1"])
    assert [
        feature["properties"]["name"]
        for feature in _artifact(subject)["features"]
    ] == ["null"]
    searched = ui.table(source, selection="multi")
    searched._search(
        SearchTableArgs(query="projected", page_size=10, page_number=0)
    )
    assert [
        feature["properties"]["name"]
        for feature in _artifact(searched)["features"]
    ] == ["projected"]
    searched._convert_value(["1"])
    assert [
        feature["properties"]["name"]
        for feature in _artifact(searched)["features"]
    ] == ["null"]
    cells = ui.table(source, selection="multi-cell")
    cells._search(
        SearchTableArgs(query="projected", page_size=10, page_number=0)
    )
    cells._convert_value([{"rowId": "1", "columnName": "name"}])
    assert [
        feature["properties"]["name"]
        for feature in _artifact(cells)["features"]
    ] == ["projected"]


def test_dataframe_transformed_value_and_obsolete_choice() -> None:
    subject = ui.dataframe(_source())
    subject._update(
        {
            "transforms": [
                {"type": "select_columns", "column_ids": ["alternate"]}
            ]
        }
    )
    assert _artifact(subject)["features"][0]["geometry"]["coordinates"] == [
        20,
        5,
    ]
    response = subject._download_geojson(
        DownloadGeoJSONArgs(format="geojson", geometry_column="location")
    )
    assert (response.url, response.code, response.column) == (
        "",
        "invalid_geometry",
        "location",
    )
    subject._value = _source().iloc[[1]].copy()
    assert [
        feature["properties"]["name"]
        for feature in _artifact(subject)["features"]
    ] == ["null"]


@pytest.mark.requires("duckdb", "geopandas", "pyarrow")
@pytest.mark.parametrize("empty", [False, True])
def test_duckdb_geojson_properties_and_secondary_wkt(
    duckdb_crs_conn: Any, widget: Any, empty: bool
) -> None:

    conn = duckdb_crs_conn
    source = fixtures.duckdb_export_relation(conn)
    if empty:
        source = source.limit(0)
    before = source.to_arrow_table()
    subject = widget(source)
    ordinary = subject._download_as(DownloadAsArgs(format="json"))
    expected = json.loads(from_data_uri(ordinary.url)[1])
    for row in expected:
        del row["geom"]
    document = _artifact(subject, "geom")
    assert "crs" not in document
    assert [f["properties"] for f in document["features"]] == expected
    if not empty:
        assert document["features"][0]["geometry"]["coordinates"] == [
            10,
            0,
        ]
        assert document["features"][1]["geometry"] is None
        assert (
            "20.1234567890123"
            in document["features"][0]["properties"]["alternate"]
        )
    assert source.to_arrow_table().equals(before, check_metadata=True)


@pytest.mark.requires("duckdb", "geopandas", "pyarrow")
def test_duckdb_geojson_projected_geometry_choice(
    duckdb_spatial_conn: Any, widget: Any
) -> None:

    conn = duckdb_spatial_conn
    try:
        source = conn.sql(
            "SELECT 'POINT (1113194.9079327357 0)'::GEOMETRY('EPSG:3857') AS projected, 'POINT (20 5)'::GEOMETRY('OGC:CRS84') AS geographic"
        )
    except Exception as e:
        pytest.skip(f"CRS-parameterized geometry unavailable: {e}")
    subject = widget(source)
    document = _artifact(subject, "projected")
    assert document["features"][0]["geometry"]["coordinates"] == pytest.approx(
        [10, 0]
    )
    assert (
        document["features"][0]["properties"]["geographic"] == "POINT (20 5)"
    )
    document = _artifact(subject, "geographic")
    assert document["features"][0]["geometry"]["coordinates"] == [20, 5]
    assert (
        "1113194.9079327357"
        in document["features"][0]["properties"]["projected"]
    )


@pytest.mark.requires("duckdb", "geopandas", "pyarrow")
def test_duckdb_geojson_missing_crs_and_alternate_choice(
    duckdb_crs_conn: Any, widget: Any
) -> None:

    conn = duckdb_crs_conn
    subject = widget(fixtures.duckdb_export_relation(conn))
    response = subject._download_geojson(
        DownloadGeoJSONArgs(format="geojson", geometry_column="alternate")
    )
    assert response.code == "missing_crs"
    assert response.column == "alternate"
    assert response.url == ""
    assert "Declare its source CRS" in response.error
    assert len(_artifact(subject, "geom")["features"]) == 3


@pytest.mark.requires("duckdb", "geopandas", "pyarrow")
def test_duckdb_geojson_effective_rows(
    duckdb_crs_conn: Any,
) -> None:

    conn = duckdb_crs_conn
    source = fixtures.duckdb_export_relation(conn)
    table = ui.table(source)
    table._update(["0", "2"])
    assert [
        f["properties"]["id"] for f in _artifact(table, "geom")["features"]
    ] == [1, 3]
    frame = ui.dataframe(source, limit=1)
    assert len(_artifact(frame, "geom")["features"]) == 3
    frame._update(
        {"transforms": [{"type": "select_columns", "column_ids": ["geom"]}]}
    )
    assert [f["properties"] for f in _artifact(frame)["features"]] == [
        {},
        {},
        {},
    ]
    searched = ui.table(source)
    searched._searched_manager = searched._manager.search("first")
    assert [
        f["properties"]["id"] for f in _artifact(searched, "geom")["features"]
    ] == [1]


@pytest.mark.requires("duckdb", "geopandas", "pyarrow")
@pytest.mark.parametrize(
    "value", ["NULL", "'POINT EMPTY'", "'POINT Z (1 2 3)'"]
)
def test_duckdb_geojson_geometry_only(
    duckdb_crs_conn: Any, widget: Any, value: str
) -> None:

    conn = duckdb_crs_conn
    subject = widget(
        conn.sql(f"SELECT {value}::GEOMETRY('OGC:CRS84') AS geom")
    )
    feature = _artifact(subject)["features"][0]
    assert feature["properties"] == {}
    if value == "NULL":
        assert feature["geometry"] is None
    elif "EMPTY" in value:
        assert (
            feature["geometry"] is None
            or feature["geometry"]["coordinates"] == []
        )
    else:
        assert feature["geometry"]["coordinates"] == [1, 2, 3]


@pytest.mark.requires("duckdb", "geopandas", "pyarrow")
@pytest.mark.parametrize("wkt", ["POINT M (1 2 3)", "POINT ZM (1 2 3 4)"])
def test_duckdb_geojson_measured_geometry_rejects(
    duckdb_crs_conn: Any, widget: Any, wkt: str
) -> None:

    conn = duckdb_crs_conn
    response = widget(
        conn.sql(f"SELECT '{wkt}'::GEOMETRY('OGC:CRS84') AS geom")
    )._download_geojson(DownloadGeoJSONArgs(format="geojson"))
    assert response.code == "unsupported_representation"
    assert response.url == ""


@pytest.mark.requires("duckdb", "geopandas", "pyarrow")
@pytest.mark.parametrize("value", ["'NaN'::DOUBLE", "'Infinity'::DOUBLE"])
def test_duckdb_geojson_nonfinite_properties_follow_json_policy(
    duckdb_crs_conn: Any, widget: Any, value: str
) -> None:

    conn = duckdb_crs_conn
    subject = widget(
        conn.sql(
            f"SELECT 'POINT (1 2)'::GEOMETRY('OGC:CRS84') AS geom, {value} AS value"
        )
    )
    response = subject._download_geojson(DownloadGeoJSONArgs(format="geojson"))
    if "NaN" in value:
        assert response.code == "conversion_failed"
        assert response.url == ""
    else:
        ordinary = subject._download_as(DownloadAsArgs(format="json"))
        expected = json.loads(from_data_uri(ordinary.url)[1])[0]
        del expected["geom"]
        assert _artifact(subject)["features"][0]["properties"] == expected


@pytest.mark.requires("duckdb", "pyarrow")
@pytest.mark.parametrize("missing", ["geopandas", "pyarrow"])
def test_duckdb_geojson_missing_packages(
    duckdb_crs_conn: Any, widget: Any, missing: str
) -> None:

    conn = duckdb_crs_conn
    subject = widget(conn.sql("SELECT NULL::GEOMETRY('OGC:CRS84') AS geom"))
    with patch.object(
        getattr(DependencyManager, missing), "has", return_value=False
    ):
        response = subject._download_geojson(
            DownloadGeoJSONArgs(format="geojson")
        )
    assert response.code == "missing_packages"
    assert response.missing_packages == [missing]
    assert response.url == ""


@pytest.mark.requires("duckdb", "geopandas", "pyarrow")
@pytest.mark.parametrize(
    "kind", ["POINT_2D", "LINESTRING_2D", "POLYGON_2D", "BOX_2D"]
)
def test_duckdb_geojson_fixed_layout_rejects(
    duckdb_spatial_conn: Any, widget: Any, kind: str
) -> None:

    conn = duckdb_spatial_conn
    response = widget(
        conn.sql(f"SELECT NULL::{kind} AS geom")
    )._download_geojson(DownloadGeoJSONArgs(format="geojson"))
    assert response.code == "unsupported_representation"
    assert response.url == ""


@pytest.mark.requires("duckdb", "geopandas", "pyarrow")
@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"[]", "invalid_metadata"),
        (b'{"crs":"123","crs_type":"srid"}', "missing_crs"),
    ],
)
def test_duckdb_geojson_declaration_rejects(
    duckdb_crs_conn: Any, widget: Any, payload: bytes, code: str
) -> None:
    import pyarrow as pa

    conn = duckdb_crs_conn
    subject = widget(
        conn.sql("SELECT 'POINT (1 2)'::GEOMETRY('OGC:CRS84') AS geom")
    )
    schema = pa.schema(
        [
            pa.field(
                "geom",
                pa.binary(),
                metadata={
                    b"ARROW:extension:name": b"geoarrow.wkb",
                    b"ARROW:extension:metadata": payload,
                },
            )
        ]
    )
    with patch(
        "marimo._plugins.ui._impl.tables.geometry_export._duckdb_geometry_schema",
        return_value=schema,
    ):
        response = subject._download_geojson(
            DownloadGeoJSONArgs(format="geojson")
        )
    assert response.code == code
    assert response.url == ""


@pytest.mark.requires("duckdb", "geopandas", "pyarrow")
def test_duckdb_unknown_crs_geojson_rejects_on_older_versions(
    duckdb_export_conn: Any,
    widget: Any,
) -> None:

    conn = duckdb_export_conn
    response = widget(
        conn.sql("SELECT 'POINT (1 2)'::GEOMETRY AS geom")
    )._download_geojson(DownloadGeoJSONArgs(format="geojson"))
    assert response.code == "missing_crs"
    assert response.url == ""


@pytest.mark.requires("duckdb", "geopandas", "pyarrow")
def test_duckdb_closed_connection_is_structured_failure() -> None:
    from marimo._plugins.ui._impl.tables.geometry_export import (
        GeometryExportError,
        has_geometry_columns,
        serialize_geojson,
    )
    from marimo._plugins.ui._impl.tables.utils import get_table_manager

    conn = fixtures.duckdb_crs_geometry_connection()
    manager = get_table_manager(
        conn.sql("SELECT NULL::GEOMETRY('OGC:CRS84') AS geom")
    )
    assert has_geometry_columns(manager)
    conn.close()
    with pytest.raises(GeometryExportError) as error:
        serialize_geojson(manager, None)
    assert error.value.code == "conversion_failed"


@pytest.mark.requires("duckdb", "geopandas", "pyarrow")
def test_duckdb_registered_wkb_preserves_crs(widget: Any) -> None:
    import pyarrow as pa

    class GeometryType(pa.ExtensionType):
        def __init__(self, metadata: bytes = b"{}") -> None:
            self.metadata = metadata
            super().__init__(pa.binary(), "geoarrow.wkb")

        def __arrow_ext_serialize__(self) -> bytes:
            return self.metadata

        @classmethod
        def __arrow_ext_deserialize__(
            cls, storage: Any, metadata: bytes
        ) -> Any:
            return cls(metadata)

    conn = fixtures.duckdb_crs_geometry_connection()
    pa.register_extension_type(GeometryType())  # type: ignore[arg-type]
    try:
        document = _artifact(
            widget(
                conn.sql("SELECT 'POINT (1 2)'::GEOMETRY('OGC:CRS84') AS geom")
            )
        )
        assert document["features"][0]["geometry"]["coordinates"] == [1, 2]
    finally:
        pa.unregister_extension_type("geoarrow.wkb")
        conn.close()

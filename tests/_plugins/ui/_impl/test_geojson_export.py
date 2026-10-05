# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._plugins.ui._impl.table import DownloadAsArgs, DownloadGeoJSONArgs
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


@pytest.mark.requires("pyarrow")
def test_arrow_geometry_is_not_exported_as_geojson(widget: Any) -> None:
    subject = widget(fixtures.arrow_wkb_known_crs())
    response = subject._download_geojson(DownloadGeoJSONArgs(format="geojson"))
    assert (response.url, response.code) == ("", "unsupported_representation")


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

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from io import BytesIO
from typing import TYPE_CHECKING, Any, Literal

import narwhals.stable.v2 as nw

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.geometry import (
    GeometryColumnInfo,
    GeometryEncoding,
    find_geometry_columns,
)
from marimo._plugins.ui._impl.tables.narwhals_table import (
    NarwhalsTableManager,
)
from marimo._plugins.ui._impl.tables.table_manager import TableManager
from marimo._sql.sql_quoting import quote_sql_identifier

if TYPE_CHECKING:
    import pyarrow as pa


GeometryExportErrorCode = Literal[
    "geometry_required",
    "invalid_geometry",
    "invalid_metadata",
    "unsupported_representation",
    "unsupported_version",
    "missing_packages",
    "missing_crs",
    "conversion_failed",
]

_MIN_GEOPANDAS_GEOPARQUET_VERSION = "0.14.1"
_GEOPANDAS_UPGRADE_MESSAGE = (
    "Update geopandas to 0.14.1 or newer to export GeoParquet."
)
_MIN_SHAPELY_GEOJSON_VERSION = "2.0"
_SHAPELY_UPGRADE_MESSAGE = "Update shapely to 2.0 or newer to export GeoJSON."


class GeometryExportError(Exception):
    """An export failure that the dialog can explain and recover from.

    Args:
        code (GeometryExportErrorCode): Machine-readable failure category.
        message (str): User-facing failure explanation.
        column (str | None, optional): Affected geometry column.
        missing_packages (list[str] | None, optional): Required packages.
    """

    def __init__(
        self,
        code: GeometryExportErrorCode,
        message: str,
        column: str | None = None,
        missing_packages: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.column = column
        self.missing_packages = missing_packages


@dataclass(frozen=True)
class ArrowGeometryDeclaration:
    """Geometry semantics declared in GeoArrow field metadata.

    Args:
        crs (str | dict[str, Any] | None): Declared CRS or opaque identifier.
        crs_type (str | None): Declared CRS representation.
        edges (str | None): Declared non-planar edge interpretation.
        error (str | None): Reason that the declaration is invalid.
    """

    crs: str | dict[str, Any] | None = None
    crs_type: str | None = None
    edges: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class GeometryExportColumn:
    """Geometry declared by the export source.

    Args:
        name (str): Name of the geometry column.
        encoding (GeometryEncoding): Declared value encoding.
        crs (str | dict[str, Any] | None): Declared CRS, when available.
    """

    name: str
    encoding: GeometryEncoding
    crs: str | dict[str, Any] | None


@dataclass(frozen=True)
class ExportFormatEligibility:
    """Known prerequisites for a format.

    Args:
        available (bool): Whether the source can use the format.
        reason (str | None): Reason when the format is unavailable.
        missing_packages (list[str]): Packages needed for the format.
    """

    available: bool
    reason: str | None = None
    missing_packages: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExportMetadata:
    """Schema-level geometry and format metadata for an export source.

    Args:
        geometry_columns (list[GeometryExportColumn]): All declared geometry
            columns, including columns outside the visible preview.
        primary_geometry_column (str | None): Valid source primary, if any.
        default_geometry_column (str | None): Primary or sole geometry.
        formats (dict[str, ExportFormatEligibility]): Eligibility for
            geometry-aware formats. The serializer checks values separately.
    """

    geometry_columns: list[GeometryExportColumn] = field(default_factory=list)
    primary_geometry_column: str | None = None
    default_geometry_column: str | None = None
    formats: dict[str, ExportFormatEligibility] = field(default_factory=dict)


def get_export_metadata(manager: TableManager[Any]) -> ExportMetadata:
    """Read geometry declarations without materializing source rows.

    Format eligibility covers source support and dependencies. The chosen
    geometry's CRS and values require separate checks.

    Args:
        manager (TableManager[Any]): Manager for the export source.
    """
    if not isinstance(manager, NarwhalsTableManager):
        return ExportMetadata()

    info_by_name = _export_geometry_columns(manager)
    if not info_by_name:
        return ExportMetadata()

    source = manager.data
    primary: str | None = None
    columns: list[GeometryExportColumn] = []
    source_reason: str | None = None
    if source.implementation.is_pandas():
        native = source.to_native()
        candidate = getattr(native, "_geometry_column_name", None)
        if isinstance(candidate, str) and candidate in info_by_name:
            primary = candidate
        for name, info in info_by_name.items():
            crs = native[name].array.crs
            columns.append(
                GeometryExportColumn(
                    name=name,
                    encoding=info.encoding,
                    crs=crs.to_string() if crs is not None else None,
                )
            )
        is_supported_source = DependencyManager.geopandas.has()
    elif source.implementation.is_pyarrow():
        native = source.to_native()
        for name, info in info_by_name.items():
            declaration = _arrow_geometry_declaration(
                native.schema.field(name)
            )
            columns.append(
                GeometryExportColumn(
                    name=name,
                    encoding=info.encoding,
                    crs=(
                        declaration.crs
                        if declaration.crs_type != "srid"
                        else None
                    ),
                )
            )
            rejection = _arrow_geometry_rejection(
                name, info.encoding, declaration
            )
            if source_reason is None and rejection is not None:
                source_reason = rejection[1]
        is_supported_source = DependencyManager.geopandas.has()
    else:
        columns = [
            GeometryExportColumn(name=name, encoding=info.encoding, crs=None)
            for name, info in info_by_name.items()
        ]
        is_supported_source = False

    formats: dict[str, ExportFormatEligibility] = {}
    if not is_supported_source:
        for format_name, label in (
            ("parquet", "GeoParquet"),
            ("geojson", "GeoJSON"),
        ):
            if (
                source.implementation.is_pandas()
                or source.implementation.is_pyarrow()
            ):
                source_label = (
                    "pandas" if source.implementation.is_pandas() else "Arrow"
                )
                reason = f"This {source_label} table needs geopandas to export {label}."
                missing_packages = ["geopandas"]
            else:
                reason = (
                    f"{label} export is not supported for this table type."
                )
                missing_packages = []
            formats[format_name] = ExportFormatEligibility(
                available=False,
                reason=reason,
                missing_packages=missing_packages,
            )
    else:
        if DependencyManager.shapely.has_at_version(
            min_version=_MIN_SHAPELY_GEOJSON_VERSION, quiet=True
        ):
            formats["geojson"] = ExportFormatEligibility(available=True)
        else:
            formats["geojson"] = ExportFormatEligibility(
                available=False, reason=_SHAPELY_UPGRADE_MESSAGE
            )
        if not DependencyManager.geopandas.has_at_version(
            min_version=_MIN_GEOPANDAS_GEOPARQUET_VERSION, quiet=True
        ):
            formats["parquet"] = ExportFormatEligibility(
                available=False,
                reason=_GEOPANDAS_UPGRADE_MESSAGE,
            )
        elif not DependencyManager.pyarrow.has():
            formats["parquet"] = ExportFormatEligibility(
                available=False,
                reason="GeoParquet export requires pyarrow.",
                missing_packages=["pyarrow"],
            )
        else:
            formats["parquet"] = ExportFormatEligibility(available=True)

    if source_reason is not None:
        formats = {
            name: ExportFormatEligibility(
                available=False, reason=source_reason
            )
            for name in ("parquet", "geojson")
        }

    default = (
        primary
        if primary is not None
        else (columns[0].name if len(columns) == 1 else None)
    )
    return ExportMetadata(
        geometry_columns=columns,
        primary_geometry_column=primary,
        default_geometry_column=default,
        formats=formats,
    )


def _arrow_geometry_declaration(
    field: pa.Field[Any],
) -> ArrowGeometryDeclaration:
    field = _arrow_storage_field(field)
    metadata = field.metadata
    if not metadata:
        return ArrowGeometryDeclaration()
    raw = metadata.get(b"ARROW:extension:metadata")
    if raw is None:
        return ArrowGeometryDeclaration()

    def invalid(reason: str) -> ArrowGeometryDeclaration:
        return ArrowGeometryDeclaration(
            error=f"Geometry column {field.name!r} has invalid GeoArrow metadata: {reason}"
        )

    try:
        declaration = json.loads(
            raw.decode("utf-8"), parse_constant=_reject_json_constant
        )
    except (ValueError, UnicodeDecodeError):
        return invalid("expected a UTF-8 JSON object.")
    if not isinstance(declaration, dict):
        return invalid("expected a JSON object.")
    crs = declaration.get("crs")
    if "crs" in declaration and not isinstance(crs, (str, dict)):
        return invalid("crs must be a string or PROJJSON object.")
    crs_type = declaration.get("crs_type")
    if "crs_type" in declaration and crs_type not in (
        "projjson",
        "wkt2:2019",
        "authority_code",
        "srid",
    ):
        return invalid("unknown crs_type.")
    if crs is not None and crs_type is not None:
        if crs_type == "projjson" and not isinstance(crs, dict):
            return invalid("projjson crs must be an object.")
        if crs_type != "projjson" and not isinstance(crs, str):
            return invalid(f"{crs_type} crs must be a string.")
    edges = declaration.get("edges")
    if "edges" in declaration and edges not in (
        "spherical",
        "vincenty",
        "thomas",
        "andoyer",
        "karney",
    ):
        return invalid("unknown edges interpretation.")
    if (
        crs is not None
        and crs_type != "srid"
        and DependencyManager.geopandas.has()
    ):
        from pyproj import CRS  # type: ignore[import-untyped]
        from pyproj.exceptions import CRSError  # type: ignore[import-untyped]

        try:
            if crs_type == "projjson":
                CRS.from_json_dict(crs)
            elif crs_type == "wkt2:2019":
                CRS.from_wkt(crs)
            elif crs_type == "authority_code":
                authority, code = crs.split(":", 1)
                CRS.from_authority(authority, code)
            else:
                CRS.from_user_input(crs)
        except (CRSError, ValueError):
            return invalid("crs cannot be resolved.")
    return ArrowGeometryDeclaration(crs=crs, crs_type=crs_type, edges=edges)


def _arrow_geometry_rejection(
    name: str,
    encoding: GeometryEncoding,
    declaration: ArrowGeometryDeclaration,
) -> tuple[GeometryExportErrorCode, str] | None:
    if declaration.error is not None:
        return "invalid_metadata", declaration.error
    if declaration.edges is not None:
        return (
            "unsupported_representation",
            (
                f"Geometry column {name!r} declares {declaration.edges!r} "
                "edges, which geographic exports cannot preserve."
            ),
        )
    if encoding not in ("wkb", "wkt"):
        return (
            "unsupported_representation",
            (
                f"Geometry column {name!r} uses a native GeoArrow layout. "
                "Geographic exports require WKB or WKT."
            ),
        )
    return None


def has_geometry_columns(manager: TableManager[Any]) -> bool:
    """Check geometry declarations without inspecting rows.

    Args:
        manager (TableManager[Any]): Manager for the export source.
    """
    return isinstance(manager, NarwhalsTableManager) and bool(
        _export_geometry_columns(manager)
    )


def _arrow_storage_field(field: pa.Field[Any]) -> pa.Field[Any]:
    import pyarrow as pa

    if not isinstance(field.type, pa.ExtensionType):
        return field
    extension = field.type
    if not (
        extension.extension_name.startswith("geoarrow.")
        or extension.extension_name == "ogc.wkb"
    ):
        return field
    metadata: dict[bytes | str, bytes | str] = {
        key: value for key, value in (field.metadata or {}).items()
    }
    metadata[b"ARROW:extension:name"] = extension.extension_name.encode()
    serialized = extension.__arrow_ext_serialize__()
    if extension.extension_name == "ogc.wkb" and not serialized:
        metadata.pop(b"ARROW:extension:metadata", None)
    else:
        metadata[b"ARROW:extension:metadata"] = serialized
    return field.with_type(extension.storage_type).with_metadata(metadata)


def _export_geometry_columns(
    manager: NarwhalsTableManager[Any, Any],
) -> dict[str, GeometryColumnInfo]:
    if not manager.data.implementation.is_pyarrow():
        return find_geometry_columns(manager.data)

    import pyarrow as pa

    schema = pa.schema(
        [
            _arrow_storage_field(field)
            for field in manager.data.to_native().schema
        ]
    )
    schema_view = pa.Table.from_batches([], schema=schema)
    return find_geometry_columns(nw.from_native(schema_view))


def _arrow_to_geodataframe(
    table: pa.Table, columns: list[GeometryExportColumn]
) -> Any:
    import geopandas as gpd  # type: ignore[import-not-found,import-untyped,unused-ignore]
    import pandas as pd
    import pyarrow as pa

    if len(set(table.column_names)) != len(table.column_names):
        raise GeometryExportError(
            "invalid_metadata",
            "Geographic exports require unique column names.",
        )
    for column in columns:
        declaration = _arrow_geometry_declaration(
            table.schema.field(column.name)
        )
        rejection = _arrow_geometry_rejection(
            column.name, column.encoding, declaration
        )
        if rejection is not None:
            raise GeometryExportError(
                rejection[0], rejection[1], column=column.name
            )

    try:
        ordinary = table.drop([column.name for column in columns]).to_pandas(
            ignore_metadata=True, types_mapper=pd.ArrowDtype
        )
        frame = gpd.GeoDataFrame(ordinary)
        for index, column in enumerate(columns):
            values = table.column(column.name)
            decoded = [
                value
                for chunk in values.chunks
                for value in (
                    chunk.storage
                    if isinstance(chunk, pa.ExtensionArray)
                    else chunk
                ).to_pylist()
            ]
            parser = (
                gpd.GeoSeries.from_wkb
                if column.encoding == "wkb"
                else gpd.GeoSeries.from_wkt
            )
            geometry = parser(decoded, crs=column.crs, index=frame.index)
            if index == 0:
                frame = frame.set_geometry(geometry.rename(column.name))
            else:
                frame[column.name] = geometry
        return frame[table.column_names]
    except Exception as e:
        raise GeometryExportError(
            "conversion_failed", f"Could not convert Arrow geometry: {e}"
        ) from e


def _export_geodataframe(
    manager: NarwhalsTableManager[Any, Any], metadata: ExportMetadata
) -> Any:
    native = manager.as_frame().to_native()
    if manager.data.implementation.is_pandas():
        return native
    if manager.data.implementation.is_pyarrow():
        return _arrow_to_geodataframe(native, metadata.geometry_columns)
    raise GeometryExportError(
        "unsupported_representation",
        "Geographic export from this table type is not supported yet.",
    )


def serialize_geojson(
    manager: TableManager[Any],
    geometry_column: str | None,
    ensure_ascii: bool = True,
) -> bytes:
    """Write selected geometry and ordinary JSON properties as RFC 7946.

    Args:
        manager (TableManager[Any]): Manager for the effective export rows.
        geometry_column (str | None): Explicit geometry, if chosen.
        ensure_ascii (bool, optional): Whether to escape non-ASCII text.

    Raises:
        GeometryExportError: If geometry or properties cannot be preserved.
    """
    if not has_geometry_columns(manager):
        raise GeometryExportError(
            "invalid_geometry"
            if geometry_column is not None
            else "geometry_required",
            "GeoJSON export requires a declared geometry column.",
            column=geometry_column,
        )
    if not isinstance(manager, NarwhalsTableManager) or not (
        manager.data.implementation.is_pandas()
        or manager.data.implementation.is_pyarrow()
    ):
        raise GeometryExportError(
            "unsupported_representation",
            "GeoJSON export from this table type is not supported yet.",
            column=geometry_column,
        )
    try:
        metadata = get_export_metadata(manager)
    except Exception as e:
        raise GeometryExportError(
            "invalid_metadata", f"Could not read geometry metadata: {e}"
        ) from e
    names = {column.name for column in metadata.geometry_columns}
    if geometry_column is not None and geometry_column not in names:
        raise GeometryExportError(
            "invalid_geometry",
            f"{geometry_column!r} is not a geometry column in this table.",
            column=geometry_column,
        )
    primary = (
        geometry_column
        if geometry_column is not None
        else metadata.default_geometry_column
    )
    if primary is None:
        raise GeometryExportError(
            "geometry_required",
            "Choose a geometry column for GeoJSON export.",
        )
    if not DependencyManager.geopandas.has():
        source_label = (
            "pandas" if manager.data.implementation.is_pandas() else "Arrow"
        )
        raise GeometryExportError(
            "missing_packages",
            f"This {source_label} table needs geopandas to export GeoJSON.",
            missing_packages=["geopandas"],
        )
    if not DependencyManager.shapely.has_at_version(
        min_version=_MIN_SHAPELY_GEOJSON_VERSION, quiet=True
    ):
        raise GeometryExportError(
            "unsupported_version", _SHAPELY_UPGRADE_MESSAGE
        )

    import geopandas as gpd  # type: ignore[import-not-found,import-untyped,unused-ignore]
    from shapely.ops import orient  # type: ignore[import-untyped]

    from marimo._plugins.ui._impl.tables.pandas_table import (
        PandasTableManagerFactory,
        _index_level_names,
        _trivial_range_index,
    )

    native = _export_geodataframe(manager, metadata)
    if not native.columns.is_unique:
        raise GeometryExportError(
            "invalid_metadata", "GeoJSON export requires unique column names."
        )
    geometry = gpd.GeoSeries(native[primary].array, index=native.index)
    exports_index = isinstance(
        manager, PandasTableManagerFactory.create()
    ) and not _trivial_range_index(native.index)
    if geometry.crs is None:
        raise GeometryExportError(
            "missing_crs",
            f"Geometry column {primary!r} needs a CRS for GeoJSON export. "
            "Declare its source CRS in Python before exporting.",
            column=primary,
        )
    try:
        if any(getattr(value, "has_m", False) for value in geometry.array):
            raise GeometryExportError(
                "unsupported_representation",
                f"Geometry column {primary!r} contains M coordinates.",
                column=primary,
            )
        projected = geometry.to_crs(epsg=4326)
        _validate_reprojection(geometry, projected, primary)
        projected = gpd.GeoSeries(
            [
                orient(value, sign=1.0)
                if value is not None
                and value.geom_type
                in ("Polygon", "MultiPolygon", "GeometryCollection")
                else value
                for value in projected.array
            ],
            index=projected.index,
            crs=projected.crs,
        )
        export = gpd.GeoDataFrame(geometry=projected)
        properties_manager = (
            _prepare_arrow_geojson_properties(manager, native, primary, names)
            if manager.data.implementation.is_pyarrow()
            else prepare_geometry_text_export(manager.drop_columns([primary]))
        )
        properties: list[dict[str, Any]]
        if len(native.columns) == 1 and not exports_index:
            properties = [{} for _ in range(len(native))]
        else:
            property_json = properties_manager.to_json_str(
                strict_json=True, ensure_ascii=ensure_ascii
            )
            properties = json.loads(
                property_json, parse_constant=_reject_json_constant
            )
            del property_json
        if not isinstance(properties, list) or len(properties) != len(native):
            raise ValueError("Property conversion changed the number of rows.")
        expected_keys = set(native.columns) - {primary}
        if exports_index:
            expected_keys.update(
                _index_level_names(native.index, expected_keys)
            )
        if any(
            not isinstance(row, dict) or set(row) != expected_keys
            for row in properties
        ):
            raise ValueError("Property conversion changed the column names.")
        _validate_secondary_wkt(properties, native, names - {primary})
        features = []
        for feature, row, value in zip(
            export.iterfeatures(drop_id=True),
            properties,
            projected.array,
            strict=True,
        ):
            if value is not None and value.is_empty:
                feature["geometry"] = (
                    {"type": "GeometryCollection", "geometries": []}
                    if value.geom_type == "GeometryCollection"
                    else {"type": value.geom_type, "coordinates": []}
                )
            expected_geometry = (
                None
                if value is None
                else feature["geometry"]
                if value.is_empty
                else value.__geo_interface__
            )
            if (
                set(feature) != {"type", "geometry", "properties"}
                or feature["type"] != "Feature"
                or feature["geometry"] != expected_geometry
            ):
                raise ValueError(
                    "Geometry serialization changed feature geometry."
                )
            if feature["geometry"] is not None:
                _validate_geojson_geometry(feature["geometry"])
            feature["properties"] = row
            features.append(feature)
        del properties
        text = json.dumps(
            {"type": "FeatureCollection", "features": features},
            allow_nan=False,
            ensure_ascii=ensure_ascii,
            separators=(",", ":"),
        )
        del features, export, projected, geometry, properties_manager
        return text.encode("utf-8")
    except GeometryExportError:
        raise
    except Exception as e:
        raise GeometryExportError(
            "conversion_failed",
            f"Could not export GeoJSON: {e}",
            column=primary,
        ) from e


def _prepare_arrow_geojson_properties(
    manager: NarwhalsTableManager[Any, Any],
    frame: Any,
    primary: str,
    geometry_columns: set[str],
) -> TableManager[Any]:
    import pyarrow as pa

    source: pa.Table = manager.as_frame().to_native()
    properties = source.drop([primary])
    for name in geometry_columns - {primary}:
        index = properties.schema.get_field_index(name)
        original = properties.schema.field(index)
        metadata = {
            key: value
            for key, value in (original.metadata or {}).items()
            if key
            not in (b"ARROW:extension:name", b"ARROW:extension:metadata")
        }
        field = pa.field(
            name,
            pa.string(),
            nullable=original.nullable,
            metadata=metadata or None,
        )
        values = pa.array(
            frame[name].to_wkt(rounding_precision=-1),
            type=pa.string(),
            from_pandas=True,
        )
        properties = properties.set_column(index, field, values)
    return _with_native_data(manager, properties)


def _reject_json_constant(value: str) -> Any:
    raise ValueError(f"Invalid JSON constant: {value}")


def _validate_reprojection(source: Any, projected: Any, column: str) -> None:
    import numpy as np
    import shapely  # type: ignore[import-untyped]

    original_coordinates = shapely.get_coordinates(
        source.array, include_z=True
    )
    projected_coordinates = shapely.get_coordinates(
        projected.array, include_z=True
    )
    if (
        not np.isfinite(original_coordinates[:, :2]).all()
        or not np.isfinite(projected_coordinates[:, :2]).all()
        or not np.array_equal(
            shapely.get_num_coordinates(source.array),
            shapely.get_num_coordinates(projected.array),
        )
        or not np.array_equal(
            shapely.get_type_id(source.array),
            shapely.get_type_id(projected.array),
        )
        or not np.array_equal(
            shapely.has_z(source.array), shapely.has_z(projected.array)
        )
    ):
        raise GeometryExportError(
            "conversion_failed",
            "Reprojection changed geometry structure or produced non-finite coordinates.",
            column=column,
        )
    if source.crs != projected.crs:
        restored = projected.to_crs(source.crs)
        restored_coordinates = shapely.get_coordinates(
            restored.array, include_z=True
        )
        if (
            original_coordinates.shape != restored_coordinates.shape
            or not np.allclose(
                original_coordinates,
                restored_coordinates,
                rtol=1e-9,
                atol=1e-8,
                equal_nan=True,
            )
        ):
            raise GeometryExportError(
                "conversion_failed",
                "Reprojection cannot preserve the source coordinates.",
                column=column,
            )


def _validate_secondary_wkt(
    properties: list[dict[str, Any]], source: Any, columns: set[str]
) -> None:
    import numpy as np
    import shapely  # type: ignore[import-untyped]

    for column in columns:
        original = source[column].array
        text = [row[column] for row in properties]
        if any(
            value is not None and not isinstance(value, str) for value in text
        ):
            raise ValueError(f"WKT conversion lost geometry in {column!r}.")
        restored = shapely.from_wkt(text)
        if np.array_equal(shapely.to_wkb(original), shapely.to_wkb(restored)):
            continue
        coordinate_options = {"include_z": True}
        if any(getattr(value, "has_m", False) for value in original):
            coordinate_options["include_m"] = True
        before = shapely.get_coordinates(original, **coordinate_options)
        after = shapely.get_coordinates(restored, **coordinate_options)
        tolerance = np.abs(before[:, :2]).max(initial=0) * 1e-15
        if (
            not np.all(
                shapely.equals_exact(original, restored, tolerance=tolerance)
                | (shapely.is_missing(original) & shapely.is_missing(restored))
            )
            or before.shape != after.shape
            or not np.allclose(
                before, after, rtol=1e-15, atol=0, equal_nan=True
            )
        ):
            raise ValueError(f"WKT conversion lost geometry in {column!r}.")


def _validate_geojson_geometry(geometry: dict[str, Any]) -> None:
    from shapely.geometry import LinearRing  # type: ignore[import-untyped]

    def position(values: Any) -> None:
        if len(values) not in (2, 3) or not all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            for value in values
        ):
            raise ValueError(
                "GeoJSON positions require two or three finite coordinates."
            )
        if not (-180 <= values[0] <= 180 and -90 <= values[1] <= 90):
            raise ValueError(
                "GeoJSON coordinates must be longitude and latitude."
            )

    def line(values: Any, minimum: int = 2) -> None:
        if values and len(values) < minimum:
            raise ValueError("GeoJSON line has too few positions.")
        for values_at_position in values:
            position(values_at_position)

    def polygon(rings: Any) -> None:
        for index, ring in enumerate(rings):
            line(ring, minimum=4)
            if (
                not ring
                or ring[0] != ring[-1]
                or LinearRing(ring).is_ccw != (index == 0)
            ):
                raise ValueError(
                    "GeoJSON polygon rings require closure and correct orientation."
                )

    coordinates = geometry.get("coordinates", [])
    match geometry["type"]:
        case "Point":
            if coordinates:
                position(coordinates)
        case "MultiPoint":
            line(coordinates, minimum=1)
        case "LineString":
            line(coordinates)
        case "MultiLineString":
            for values in coordinates:
                line(values)
        case "Polygon":
            polygon(coordinates)
        case "MultiPolygon":
            for rings in coordinates:
                polygon(rings)
        case "GeometryCollection":
            for child in geometry["geometries"]:
                _validate_geojson_geometry(child)
        case _:
            raise ValueError("Unsupported GeoJSON geometry type.")


def serialize_geoparquet(
    manager: TableManager[Any], geometry_column: str | None
) -> bytes | None:
    """Write declared geometry as GeoParquet 1.0.0.

    Args:
        manager (TableManager[Any]): Manager for the effective export rows.
        geometry_column (str | None): Explicit primary geometry, if chosen.

    Returns:
        bytes | None: GeoParquet bytes, or None for an ordinary table.

    Raises:
        GeometryExportError: If a geometry source cannot produce valid
            GeoParquet or the requested primary is invalid.
    """
    if not has_geometry_columns(manager):
        if geometry_column is not None:
            raise GeometryExportError(
                "invalid_geometry",
                f"{geometry_column!r} is not a geometry column in this table.",
                column=geometry_column,
            )
        return None

    if not isinstance(manager, NarwhalsTableManager) or not (
        manager.data.implementation.is_pandas()
        or manager.data.implementation.is_pyarrow()
    ):
        raise GeometryExportError(
            "unsupported_representation",
            "GeoParquet export from this table type is not supported yet.",
            column=geometry_column,
        )

    if manager.data.implementation.is_pandas():
        if not manager.as_frame().to_native().columns.is_unique:
            raise GeometryExportError(
                "invalid_metadata",
                "GeoParquet export requires unique column names.",
            )

    try:
        metadata = get_export_metadata(manager)
    except Exception as e:
        raise GeometryExportError(
            "invalid_metadata", f"Could not read geometry metadata: {e}"
        ) from e

    names = {column.name for column in metadata.geometry_columns}
    if geometry_column is not None and geometry_column not in names:
        raise GeometryExportError(
            "invalid_geometry",
            f"{geometry_column!r} is not a geometry column in this table.",
            column=geometry_column,
        )
    primary = (
        geometry_column
        if geometry_column is not None
        else metadata.default_geometry_column
    )
    if primary is None:
        raise GeometryExportError(
            "geometry_required",
            "Choose a primary geometry column for GeoParquet export.",
        )

    if not DependencyManager.geopandas.has():
        source_label = (
            "pandas" if manager.data.implementation.is_pandas() else "Arrow"
        )
        raise GeometryExportError(
            "missing_packages",
            f"This {source_label} table needs geopandas to export GeoParquet.",
            missing_packages=["geopandas"],
        )
    if not DependencyManager.geopandas.has_at_version(
        min_version=_MIN_GEOPANDAS_GEOPARQUET_VERSION, quiet=True
    ):
        raise GeometryExportError(
            "unsupported_version", _GEOPANDAS_UPGRADE_MESSAGE
        )
    if not DependencyManager.pyarrow.has():
        raise GeometryExportError(
            "missing_packages",
            "GeoParquet export requires pyarrow.",
            missing_packages=["pyarrow"],
        )

    import geopandas as gpd  # type: ignore[import-not-found,import-untyped,unused-ignore]

    native = _export_geodataframe(manager, metadata)
    if not native.columns.is_unique:
        raise GeometryExportError(
            "invalid_metadata",
            "GeoParquet export requires unique column names.",
        )

    for name in names:
        for geometry in native[name].array:
            if geometry is not None and getattr(geometry, "has_m", False):
                raise GeometryExportError(
                    "unsupported_representation",
                    f"Geometry column {name!r} contains M coordinates.",
                    column=name,
                )

    try:
        export_frame = gpd.GeoDataFrame(
            native.copy(deep=True), geometry=primary
        )
        buffer = BytesIO()
        export_frame.to_parquet(
            buffer,
            index=None,
            schema_version="1.0.0",
        )
        artifact = buffer.getvalue()
        _validate_geoparquet(artifact, export_frame, primary, names)
    except GeometryExportError:
        raise
    except Exception as e:
        raise GeometryExportError(
            "conversion_failed",
            f"Could not export GeoParquet: {e}",
            column=primary,
        ) from e
    return artifact


def _validate_geoparquet(
    artifact: bytes,
    source: Any,
    primary: str,
    geometry_columns: set[str],
) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    from pyproj import CRS  # type: ignore[import-not-found,import-untyped,unused-ignore]

    try:
        file_metadata = pq.read_metadata(BytesIO(artifact))
    except Exception as e:
        raise GeometryExportError(
            "invalid_metadata", "The GeoParquet file is not valid Parquet."
        ) from e
    raw_geo = (file_metadata.metadata or {}).get(b"geo")
    if raw_geo is None:
        raise GeometryExportError(
            "invalid_metadata", "The GeoParquet file has no geo metadata."
        )
    try:
        geo = json.loads(raw_geo)
    except (ValueError, UnicodeDecodeError) as e:
        raise GeometryExportError(
            "invalid_metadata", "The GeoParquet metadata is not valid JSON."
        ) from e
    if (
        not isinstance(geo, dict)
        or geo.get("version") != "1.0.0"
        or geo.get("primary_column") != primary
        or not isinstance(geo.get("columns"), dict)
        or set(geo["columns"]) != geometry_columns
    ):
        raise GeometryExportError(
            "invalid_metadata", "The GeoParquet file metadata is incomplete."
        )
    schema = file_metadata.schema.to_arrow_schema()
    for name in geometry_columns:
        column = geo["columns"][name]
        if (
            not isinstance(column, dict)
            or column.get("encoding") != "WKB"
            or not isinstance(column.get("geometry_types"), list)
            or "crs" not in column
            or name not in schema.names
            or not pa.types.is_binary(
                _arrow_storage_field(schema.field(name)).type
            )
        ):
            raise GeometryExportError(
                "invalid_metadata",
                f"The GeoParquet metadata for {name!r} is invalid.",
                column=name,
            )
        expected_crs = source[name].crs
        stored_crs = column["crs"]
        if expected_crs is None:
            valid_crs = stored_crs is None
        else:
            try:
                valid_crs = isinstance(stored_crs, dict) and (
                    CRS.from_json_dict(stored_crs) == expected_crs
                )
            except Exception:
                valid_crs = False
        if not valid_crs:
            raise GeometryExportError(
                "invalid_metadata",
                f"The GeoParquet CRS for {name!r} is invalid.",
                column=name,
            )


def prepare_geometry_text_export(
    manager: TableManager[Any],
) -> TableManager[Any]:
    """Create an export view with complete geometry text.

    Args:
        manager (TableManager[Any]): The manager for the effective export
            rows.

    Returns:
        TableManager[Any]: A manager with supported geometry columns replaced
            by complete WKT or lossless hexadecimal WKB text.
    """
    if not isinstance(manager, NarwhalsTableManager):
        return manager

    geometry_columns = manager._geometry_columns
    if not geometry_columns:
        return manager

    source_frame = manager.data
    if source_frame.implementation.is_duckdb():
        return _prepare_duckdb_export(manager, geometry_columns)

    frame = manager.as_frame()
    if frame.implementation.is_pandas():
        return _prepare_pandas_export(manager, geometry_columns)
    if frame.implementation.is_pyarrow():
        return _prepare_arrow_export(manager, geometry_columns)
    return manager


def _prepare_pandas_export(
    manager: NarwhalsTableManager[Any, Any],
    geometry_columns: dict[str, GeometryColumnInfo],
) -> TableManager[Any]:
    import geopandas as gpd  # type: ignore[import-not-found,import-untyped,unused-ignore]
    import pandas as pd

    native = manager.as_frame().to_native()
    export_frame = pd.DataFrame(native.copy())
    converted = False

    for column, info in geometry_columns.items():
        if info.encoding != "objects":
            continue
        geometry = gpd.GeoSeries(
            native[column].array,
            index=native.index,
        )
        export_frame[column] = geometry.to_wkt(rounding_precision=-1)
        converted = True

    return _with_native_data(manager, export_frame) if converted else manager


def _prepare_arrow_export(
    manager: NarwhalsTableManager[Any, Any],
    geometry_columns: dict[str, GeometryColumnInfo],
) -> TableManager[Any]:
    import pyarrow as pa

    export_table: pa.Table = manager.as_frame().to_native()
    converted = False

    for column, info in geometry_columns.items():
        if info.encoding not in ("wkt", "wkb"):
            continue

        index = export_table.schema.get_field_index(column)
        field = export_table.schema.field(index)
        metadata = dict(field.metadata or {})
        metadata.pop(b"ARROW:extension:name", None)
        metadata.pop(b"ARROW:extension:metadata", None)
        export_type = pa.string() if info.encoding == "wkb" else field.type
        export_field = pa.field(
            field.name,
            export_type,
            nullable=field.nullable,
            metadata=metadata or None,
        )

        values = export_table.column(index)
        export_values: pa.Array[Any] | pa.ChunkedArray[Any]
        if info.encoding == "wkb":
            export_values = pa.array(
                _wkb_values_to_text(values.to_pylist()),
                type=pa.string(),
            )
        else:
            export_values = values

        export_table = export_table.set_column(
            index, export_field, export_values
        )
        converted = True

    return _with_native_data(manager, export_table) if converted else manager


def _wkb_values_to_text(values: list[Any]) -> list[str | None]:
    if not DependencyManager.shapely.has():
        return [
            None if value is None else bytes(value).hex() for value in values
        ]

    from shapely import wkb, wkt  # type: ignore[import-untyped]

    return [
        (
            None
            if value is None
            else wkt.dumps(
                wkb.loads(bytes(value)),
                rounding_precision=-1,
                trim=True,
            )
        )
        for value in values
    ]


def _prepare_duckdb_export(
    manager: NarwhalsTableManager[Any, Any],
    geometry_columns: dict[str, GeometryColumnInfo],
) -> TableManager[Any]:
    relation = manager.data.to_native()
    expressions: list[str] = []
    converted = False

    for column in relation.columns:
        quoted = quote_sql_identifier(column, dialect="duckdb")
        info = geometry_columns.get(column)
        if (
            info is not None
            and info.encoding == "wkb"
            and info.external_type.startswith("GEOMETRY")
        ):
            expressions.append(f"ST_AsText({quoted}) AS {quoted}")
            converted = True
        else:
            expressions.append(quoted)

    if not converted:
        return manager
    return _with_native_data(manager, relation.project(", ".join(expressions)))


def _with_native_data(
    manager: NarwhalsTableManager[Any, Any], native: Any
) -> TableManager[Any]:
    return manager.with_new_data(nw.from_native(native, pass_through=False))

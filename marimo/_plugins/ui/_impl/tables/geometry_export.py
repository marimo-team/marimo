# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

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

    Args:
        manager (TableManager[Any]): Manager for the export source.
    """
    if not isinstance(manager, NarwhalsTableManager):
        return ExportMetadata()

    info_by_name = find_geometry_columns(manager.data)
    if not info_by_name:
        return ExportMetadata()

    source = manager.data
    primary: str | None = None
    columns: list[GeometryExportColumn] = []
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
        is_geodataframe = DependencyManager.geopandas.has() and isinstance(
            native, _geodataframe_type()
        )
    elif source.implementation.is_pyarrow():
        native = source.to_native()
        for name, info in info_by_name.items():
            columns.append(
                GeometryExportColumn(
                    name=name,
                    encoding=info.encoding,
                    crs=_arrow_crs(native.schema.field(name).metadata),
                )
            )
        is_geodataframe = False
    else:
        columns = [
            GeometryExportColumn(name=name, encoding=info.encoding, crs=None)
            for name, info in info_by_name.items()
        ]
        is_geodataframe = False

    if not is_geodataframe:
        parquet = ExportFormatEligibility(
            available=False,
            reason=(
                "GeoParquet export requires a GeoDataFrame source. "
                "Convert the source to a GeoDataFrame before export."
            ),
        )
    elif not DependencyManager.pyarrow.has():
        parquet = ExportFormatEligibility(
            available=False,
            reason="GeoParquet export requires pyarrow.",
            missing_packages=["pyarrow"],
        )
    else:
        parquet = ExportFormatEligibility(available=True)

    default = primary or (columns[0].name if len(columns) == 1 else None)
    return ExportMetadata(
        geometry_columns=columns,
        primary_geometry_column=primary,
        default_geometry_column=default,
        formats={"parquet": parquet},
    )


def _geodataframe_type() -> type[Any]:
    import geopandas as gpd  # type: ignore[import-not-found,import-untyped,unused-ignore]

    return gpd.GeoDataFrame  # type: ignore[no-any-return]


def _arrow_crs(
    metadata: dict[bytes, bytes] | None,
) -> str | dict[str, Any] | None:
    if not metadata:
        return None
    raw = metadata.get(b"ARROW:extension:metadata")
    if raw is None:
        return None
    try:
        declaration = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(declaration, dict):
        return None
    crs = declaration.get("crs")
    return crs if isinstance(crs, (str, dict)) else None


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

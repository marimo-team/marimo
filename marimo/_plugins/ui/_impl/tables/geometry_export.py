# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import narwhals.stable.v2 as nw

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.geometry import GeometryColumnInfo
from marimo._plugins.ui._impl.tables.narwhals_table import (
    NarwhalsTableManager,
)
from marimo._plugins.ui._impl.tables.table_manager import TableManager
from marimo._sql.sql_quoting import quote_sql_identifier

if TYPE_CHECKING:
    import pyarrow as pa


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

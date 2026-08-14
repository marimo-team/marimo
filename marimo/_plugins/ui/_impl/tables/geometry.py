# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from marimo import _loggers

if TYPE_CHECKING:
    import narwhals.stable.v2 as nw
    import pandas as pd
    import pyarrow as pa

LOGGER = _loggers.marimo_logger()

GeometryEncoding = Literal["objects", "wkb", "wkt", "other"]

GEOMETRY_CELL_CAP = 512


@dataclass(frozen=True)
class GeometryColumnInfo:
    """How a detected geometry column stores its values.

    Args:
        encoding (GeometryEncoding): The value encoding. The value is
            `objects` for shapely scalars, `wkb` for WKB bytes, `wkt` for WKT
            strings, or `other` for typing-only detection.
        external_type (str): The native type string that users see.
    """

    encoding: GeometryEncoding
    external_type: str


def find_geometry_columns(
    frame: nw.DataFrame[Any] | nw.LazyFrame[Any],
) -> dict[str, GeometryColumnInfo]:
    """Detect geometry columns from the declared schema of a frame.

    This function returns an empty map if detection fails. A detection error
    must not prevent an ordinary table from loading.
    """
    try:
        if frame.implementation.is_pandas():
            return _pandas_geometry_columns(frame.to_native())
        if frame.implementation.is_pyarrow():
            return _pyarrow_geometry_columns(frame.to_native())
    except Exception as e:
        LOGGER.debug("Geometry detection failed: %s", e)
    return {}


def _pandas_geometry_columns(
    native: pd.DataFrame,
) -> dict[str, GeometryColumnInfo]:
    infos: dict[str, GeometryColumnInfo] = {}
    for name, dtype in native.dtypes.items():
        if str(dtype) == "geometry":
            infos[str(name)] = GeometryColumnInfo(
                encoding="objects", external_type="geometry"
            )
    return infos


# GeoArrow stores its type name in each field's ARROW:extension:name metadata.
_WKB_EXTENSION_NAMES = ("geoarrow.wkb", "ogc.wkb")
_WKT_EXTENSION_NAME = "geoarrow.wkt"
_GEOARROW_PREFIX = "geoarrow."


def _pyarrow_geometry_columns(
    native: pa.Table,
) -> dict[str, GeometryColumnInfo]:
    """Detect geometry columns from pyarrow field metadata only."""
    infos: dict[str, GeometryColumnInfo] = {}
    for field in native.schema:
        metadata = field.metadata
        if not metadata:
            continue
        raw_name = metadata.get(b"ARROW:extension:name")
        if raw_name is None:
            continue
        extension_name = raw_name.decode()
        encoding: GeometryEncoding
        if extension_name in _WKB_EXTENSION_NAMES:
            encoding = "wkb"
        elif extension_name == _WKT_EXTENSION_NAME:
            encoding = "wkt"
        elif extension_name.startswith(_GEOARROW_PREFIX):
            # Other geoarrow.* types (e.g. point) are geometry for typing only.
            encoding = "other"
        else:
            # Non-geo Arrow extensions (e.g. arrow.uuid) stay ordinary columns.
            continue
        infos[field.name] = GeometryColumnInfo(
            encoding=encoding, external_type=extension_name
        )
    return infos


def format_geometry_cell(value: Any, encoding: GeometryEncoding) -> Any:
    """Render one geometry cell for the table payload.

    WKB bytes become a size placeholder. Object and WKT values become text
    with a maximum length of `GEOMETRY_CELL_CAP` characters. Other values pass
    through unchanged.
    """
    if value is None:
        return value
    if encoding == "wkb":
        if isinstance(value, (bytes, bytearray)):
            return f"<geometry, {len(value)} B>"
        return value
    if encoding in ("objects", "wkt"):
        text = str(value)
        if len(text) > GEOMETRY_CELL_CAP:
            return text[:GEOMETRY_CELL_CAP] + "..."
        return text
    return value

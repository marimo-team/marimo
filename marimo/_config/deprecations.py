# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from msgspec.inspect import (
    DictType,
    Metadata,
    StructType,
    Type as MsgspecType,
    UnionType,
    type_info,
)

from marimo import _loggers
from marimo._config.config_schema import MarimoConfig
from marimo._config.provenance import (
    ConfigLayer,
    ConfigPath,
    format_config_source,
)
from marimo._config.resolver import config_paths
from marimo._config.schema_utils import config_leaf_types

if TYPE_CHECKING:
    from collections.abc import Iterator

LOGGER = _loggers.marimo_logger()


@cache
def _config_type_info() -> MsgspecType:
    return type_info(MarimoConfig)


def _deprecated_fields(
    annotation: MsgspecType, value: object, path: ConfigPath = ()
) -> Iterator[tuple[ConfigPath, str]]:
    if isinstance(annotation, Metadata):
        if (annotation.extra or {}).get("deprecated"):
            guidance = (annotation.extra_json_schema or {}).get(
                "description", ""
            )
            yield path, guidance
            return
        annotation = annotation.type
    if isinstance(annotation, UnionType):
        for variant in annotation.types:
            yield from _deprecated_fields(variant, value, path)
    elif isinstance(annotation, StructType):
        if isinstance(value, dict):
            for item in annotation.fields:
                if item.encode_name in value:
                    yield from _deprecated_fields(
                        item.type,
                        value[item.encode_name],
                        (*path, item.encode_name),
                    )
    elif isinstance(annotation, DictType) and isinstance(value, dict):
        for entry in value.values():
            # Record keys are user values, so keep them out of diagnostics.
            yield from _deprecated_fields(
                annotation.value_type, entry, (*path, "*")
            )


@cache
def _warn_deprecated_field(
    path: ConfigPath, source: str, guidance: str
) -> None:
    LOGGER.warning(
        "Configuration field %s from %s is deprecated.%s",
        ".".join(path),
        source,
        f" {guidance}" if guidance else "",
        extra={"omit_log_prefix": True},
    )


def warn_deprecated_fields(layer: ConfigLayer) -> None:
    """Warn once per explicitly supplied deprecated field and source."""
    if layer.source in ("default", "inferred"):
        return
    for path, guidance in _deprecated_fields(
        _config_type_info(), layer.config
    ):
        source_paths = (
            config_paths(
                layer.config,
                leaf_paths=frozenset(config_leaf_types(MarimoConfig)),
            )
            if layer.source == "env_var"
            else (path,)
        )
        for supplied in source_paths:
            if all(
                field == "*" or field == key
                for field, key in zip(path, supplied, strict=False)
            ):
                _warn_deprecated_field(
                    path,
                    format_config_source(supplied, layer.source),
                    guidance,
                )

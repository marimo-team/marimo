# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import types
from functools import cache
from typing import TYPE_CHECKING, Annotated, Any, Union, get_args, get_origin

from msgspec import Meta
from msgspec.structs import fields

from marimo import _loggers
from marimo._config.config_schema import MarimoConfig
from marimo._config.provenance import (
    ConfigLayer,
    ConfigPath,
    format_config_source,
)
from marimo._config.resolver import config_paths
from marimo._config.schema_utils import Config, config_leaf_types

if TYPE_CHECKING:
    from collections.abc import Iterator

LOGGER = _loggers.marimo_logger()


def _deprecated_fields(
    annotation: Any, value: object, path: ConfigPath = ()
) -> Iterator[tuple[ConfigPath, str]]:
    if get_origin(annotation) is Annotated:
        annotation, *extras = get_args(annotation)
        for metadata in extras:
            if isinstance(metadata, Meta) and (metadata.extra or {}).get(
                "deprecated"
            ):
                yield path, metadata.description or ""
                return
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        for variant in get_args(annotation):
            yield from _deprecated_fields(variant, value, path)
    elif isinstance(annotation, type) and issubclass(annotation, Config):
        if isinstance(value, dict):
            for item in fields(annotation):
                if item.encode_name in value:
                    yield from _deprecated_fields(
                        item.type,
                        value[item.encode_name],
                        (*path, item.encode_name),
                    )
    elif origin is dict and isinstance(value, dict):
        for entry in value.values():
            # Record keys are user values, so keep them out of diagnostics.
            yield from _deprecated_fields(
                get_args(annotation)[1], entry, (*path, "*")
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
    for path, guidance in _deprecated_fields(MarimoConfig, layer.config):
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

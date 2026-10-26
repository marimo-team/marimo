# Copyright 2026 Marimo. All rights reserved.
"""Compatibility helpers for typed user configuration."""

from __future__ import annotations

import copy
import types
from functools import cache
from typing import (
    Annotated,
    Any,
    ClassVar,
    Self,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

import msgspec
from msgspec import UNSET, Meta
from msgspec.structs import fields


def default_if_unset(value: Any, default: Any) -> Any:
    """Use a fallback only for absent values, preserving explicit None."""
    return default if value is UNSET else value


def _prepare_mcp_config(
    values: dict[str, object], path: tuple[str, ...] | None
) -> dict[str, object]:
    """Infer internal union tags without changing the user's MCP format."""
    prepared = copy.deepcopy(values)
    section: Any = prepared
    for key in path or ():
        if not isinstance(section, dict) or key not in section:
            return prepared
        section = section[key]
    if path is not None and isinstance(section, dict):
        servers = section.get("mcpServers")
        if isinstance(servers, dict):
            for server in servers.values():
                if isinstance(server, dict):
                    # Keep the legacy command-first selection for ambiguous inputs.
                    if "command" in server:
                        server["__marimo_transport__"] = "stdio"
                    elif "url" in server:
                        server["__marimo_transport__"] = "http"
    return prepared


def _retain_unknown_fields(value: object, source: object) -> None:
    """Keep unknown settings at every level for lossless load/save cycles."""
    if isinstance(value, Config) and isinstance(source, dict):
        names = {item.encode_name for item in fields(value)}
        value._extra_fields = copy.deepcopy(
            {key: item for key, item in source.items() if key not in names}
        )
        for item in fields(value):
            if item.encode_name in source:
                _retain_unknown_fields(
                    getattr(value, item.name), source[item.encode_name]
                )
    elif isinstance(value, dict) and isinstance(source, dict):
        for key, item in value.items():
            if key in source:
                _retain_unknown_fields(item, source[key])
    elif isinstance(value, list) and isinstance(source, list):
        for item, original in zip(value, source, strict=True):
            _retain_unknown_fields(item, original)


def _restore_unknown_fields(value: object, serialized: Any) -> Any:
    """Restore retained settings and remove internal MCP discriminators."""
    if isinstance(value, Config):
        tag_field = value.__struct_config__.tag_field
        if value.__struct_config__.tag is not None:
            serialized.pop(tag_field, None)
        for item in fields(value):
            if item.encode_name in serialized:
                serialized[item.encode_name] = _restore_unknown_fields(
                    getattr(value, item.name), serialized[item.encode_name]
                )
        return {
            **copy.deepcopy(value._extra_fields),
            **serialized,
        }
    if isinstance(value, dict):
        return {
            key: _restore_unknown_fields(item, serialized[key])
            for key, item in value.items()
            if key in serialized
        }
    if isinstance(value, list):
        return [
            _restore_unknown_fields(item, encoded)
            for item, encoded in zip(value, serialized, strict=True)
        ]
    return serialized


class Config(msgspec.Struct, dict=True, kw_only=True):
    """Base for user settings with presence tracking and unknown-key retention."""

    _mcp_path: ClassVar[tuple[str, ...] | None] = None

    def __post_init__(self) -> None:
        self._extra_fields: dict[str, object] = {}

    def __rich_repr__(self) -> list[tuple[str, Any]]:
        metadata = {
            name: metadata
            for name, annotation in get_type_hints(
                type(self), include_extras=True
            ).items()
            if get_origin(annotation) is Annotated
            for metadata in get_args(annotation)[1:]
            if isinstance(metadata, Meta)
        }
        return [
            (item.name, getattr(self, item.name))
            for item in fields(self)
            if not (metadata.get(item.name, Meta()).extra or {}).get(
                "sensitive"
            )
        ]

    def __repr__(self) -> str:
        values = ", ".join(
            f"{name}={value!r}" for name, value in self.__rich_repr__()
        )
        return f"{type(self).__name__}({values})"

    @classmethod
    def from_dict(cls, values: dict[str, object]) -> Self:
        """Validate settings, retaining unknown keys and legacy MCP inputs."""
        config = msgspec.convert(
            _prepare_mcp_config(values, cls._mcp_path), type=cls
        )
        _retain_unknown_fields(config, values)
        return config

    def to_dict(self) -> dict[str, Any]:
        """Serialize settings without unset fields or internal MCP tags."""
        serialized: dict[str, Any] = _restore_unknown_fields(
            self, msgspec.to_builtins(self)
        )
        return serialized


@cache
def config_leaf_types(cls: type[Config]) -> dict[tuple[str, ...], Any]:
    """Discover declared settings, treating collections as whole values."""
    leaves: dict[tuple[str, ...], Any] = {}
    for item in fields(cls):
        annotation = item.type
        if get_origin(annotation) is Annotated:
            annotation = get_args(annotation)[0]
        variants = (
            get_args(annotation)
            if get_origin(annotation) in (Union, types.UnionType)
            else (annotation,)
        )
        present = [arg for arg in variants if arg is not msgspec.UnsetType]
        nested = present[0] if len(present) == 1 else None
        if isinstance(nested, type) and issubclass(nested, Config):
            for path, leaf_type in config_leaf_types(nested).items():
                leaves[(item.encode_name, *path)] = leaf_type
        else:
            leaves[(item.encode_name,)] = annotation
    return leaves

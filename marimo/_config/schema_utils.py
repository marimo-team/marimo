# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import copy
import sys
import types
from collections.abc import Mapping
from dataclasses import MISSING, dataclass, fields
from typing import (
    Any,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from msgspec import UNSET

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


def default_if_unset(value: Any, default: Any) -> Any:
    """Use a fallback only for absent values, preserving explicit None."""
    return default if value is UNSET else value


def _resolve_field_type_hints(cls: type[Config]) -> dict[str, object]:
    return get_type_hints(cls)


def _convert_config_value(value: object, annotation: object) -> object:
    if value is None or value is UNSET:
        return value
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (Union, types.UnionType):
        for candidate in args:
            if isinstance(candidate, type) and issubclass(candidate, Config):
                if isinstance(value, candidate):
                    return value
                if isinstance(value, Mapping):
                    required = {
                        f.name
                        for f in fields(candidate)
                        if f.default is MISSING
                        and f.default_factory is MISSING
                    }
                    if required <= value.keys():
                        return candidate.from_dict(value)
            elif get_origin(candidate) in (list, dict):
                if isinstance(value, get_origin(candidate)):
                    return _convert_config_value(value, candidate)
        return value
    if isinstance(annotation, type) and issubclass(annotation, Config):
        if isinstance(value, Mapping) and not isinstance(value, annotation):
            return annotation.from_dict(value)
    if origin is list and isinstance(value, list):
        return [_convert_config_value(item, args[0]) for item in value]
    if origin is dict and isinstance(value, dict):
        return {
            key: _convert_config_value(item, args[1])
            for key, item in value.items()
        }
    return value


def serialize_config_value(value: object) -> Any:
    """Serialize configuration, omitting absent fields and retaining nulls."""
    if isinstance(value, Config):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {
            key: serialize_config_value(item)
            for key, item in value.items()
            if item is not UNSET
        }
    if isinstance(value, list):
        return [serialize_config_value(item) for item in value]
    return copy.deepcopy(value)


@dataclass(kw_only=True)
class Config:
    """Base for typed configuration sections with explicit field presence."""

    def __post_init__(self) -> None:
        self._extra_fields: dict[str, object] = {}
        for name, annotation in _resolve_field_type_hints(type(self)).items():
            setattr(
                self,
                name,
                _convert_config_value(getattr(self, name), annotation),
            )

    @classmethod
    def from_dict(cls, values: Mapping[str, object]) -> Self:
        """Construct typed sections, retaining unknown keys for compatibility."""
        names = {item.name for item in fields(cls)}
        config = cls(
            **{key: value for key, value in values.items() if key in names}
        )
        config._extra_fields = copy.deepcopy(
            {key: value for key, value in values.items() if key not in names}
        )
        return config

    def to_dict(self) -> dict[str, object]:
        """Omit unset fields while retaining fields explicitly set to None."""
        return {
            **serialize_config_value(self._extra_fields),
            **{
                item.name: serialize_config_value(getattr(self, item.name))
                for item in fields(self)
                if getattr(self, item.name) is not UNSET
            },
        }

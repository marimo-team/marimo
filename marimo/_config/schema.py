# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import copy
import sys
import types
from collections.abc import Mapping
from dataclasses import MISSING, dataclass, fields
from typing import (
    Any,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from msgspec import UNSET, UnsetType

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

T = TypeVar("T")
U = TypeVar("U")


@overload
def value_or(value: T | UnsetType | None, default: None) -> T | None: ...


@overload
def value_or(value: T | UnsetType, default: U) -> T | U: ...


def value_or(value: Any, default: Any) -> Any:
    """Use a fallback only for absent values, preserving explicit None."""
    return default if value is UNSET else value


def _field_types(cls: type[Any]) -> dict[str, Any]:
    return get_type_hints(cls)


def _convert(value: Any, annotation: Any) -> Any:
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
                    return _convert(value, candidate)
        return value
    if isinstance(annotation, type) and issubclass(annotation, Config):
        if isinstance(value, Mapping) and not isinstance(value, annotation):
            return annotation.from_dict(value)
    if origin is list and isinstance(value, list):
        return [_convert(item, args[0]) for item in value]
    if origin is dict and isinstance(value, dict):
        return {key: _convert(item, args[1]) for key, item in value.items()}
    return value


def config_to_dict(value: Any) -> Any:
    """Serialize configuration, omitting absent fields and retaining nulls."""
    if isinstance(value, Config):
        return {
            **config_to_dict(value._extra_fields),
            **{
                item.name: config_to_dict(getattr(value, item.name))
                for item in fields(value)
                if getattr(value, item.name) is not UNSET
            },
        }
    if isinstance(value, Mapping):
        return {
            key: config_to_dict(item)
            for key, item in value.items()
            if item is not UNSET
        }
    if isinstance(value, list):
        return [config_to_dict(item) for item in value]
    return copy.deepcopy(value)


@dataclass(kw_only=True)
class Config:
    """Base for typed configuration sections with explicit field presence."""

    def __post_init__(self) -> None:
        self._extra_fields: dict[str, Any] = {}
        for name, annotation in _field_types(type(self)).items():
            setattr(self, name, _convert(getattr(self, name), annotation))

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> Self:
        """Construct typed sections, retaining unknown keys for compatibility."""
        names = {item.name for item in fields(cls)}
        config = cast(
            Self,
            cast(Any, cls)(
                **{key: value for key, value in values.items() if key in names}
            ),
        )
        config._extra_fields = copy.deepcopy(
            {key: value for key, value in values.items() if key not in names}
        )
        return config

    def to_dict(self) -> dict[str, Any]:
        """Omit unset fields while retaining fields explicitly set to None."""
        return cast(dict[str, Any], config_to_dict(self))

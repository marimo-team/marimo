# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import copy
import types
from functools import cache
from typing import Annotated, Any, TypeVar, Union, get_args, get_origin

from msgspec import Meta
from msgspec.structs import fields

from marimo._config.config import PartialMarimoConfig
from marimo._config.config_schema import MarimoConfig
from marimo._config.schema_utils import Config

SECRET_PLACEHOLDER = "********"


def redact_secrets_partial(config: PartialMarimoConfig) -> PartialMarimoConfig:
    """Return a sparse configuration copy with sensitive values redacted."""
    return _redact_dict(config)


def redact_secrets(config: MarimoConfig) -> MarimoConfig:
    return MarimoConfig.from_dict(_redact_dict(config.to_dict()))


@cache
def _sensitive_paths(annotation: Any) -> tuple[tuple[str, ...], ...]:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Annotated:
        if any(
            isinstance(extra, Meta) and (extra.extra or {}).get("sensitive")
            for extra in args[1:]
        ):
            return ((),)
        return _sensitive_paths(args[0])
    if isinstance(annotation, type) and issubclass(annotation, Config):
        return tuple(
            (item.encode_name, *path)
            for item in fields(annotation)
            for path in _sensitive_paths(item.type)
        )
    if origin in (Union, types.UnionType):
        return tuple(
            dict.fromkeys(
                path for arg in args for path in _sensitive_paths(arg)
            )
        )
    if origin in (dict, list):
        return tuple(("*", *path) for path in _sensitive_paths(args[-1]))
    return ()


def _redact_dict(config: PartialMarimoConfig) -> PartialMarimoConfig:
    """Return a configuration copy with sensitive values redacted."""

    def deep_remove_from_path(path: tuple[str, ...], obj: object) -> None:
        if not path:
            return
        if isinstance(obj, list):
            remaining = path[1:] if path[0] == "*" else path
            for item in obj:
                deep_remove_from_path(remaining, item)
            return
        if not isinstance(obj, dict):
            return

        key, *remaining_path = path
        if key == "*":
            for value in obj.values():
                deep_remove_from_path(tuple(remaining_path), value)
        elif key in obj:
            if remaining_path:
                deep_remove_from_path(tuple(remaining_path), obj[key])
            elif obj[key]:
                if isinstance(obj[key], (list, dict)):
                    del obj[key]
                else:
                    obj[key] = SECRET_PLACEHOLDER

    new_config = copy.deepcopy(config)

    for path in _sensitive_paths(MarimoConfig):
        deep_remove_from_path(path, new_config)

    return new_config


T = TypeVar("T")


def remove_secret_placeholders(config: T) -> T:
    def deep_remove(obj: Any) -> Any:
        if isinstance(obj, dict):
            # Filter all keys with value SECRET_PLACEHOLDER
            return {
                k: deep_remove(v)
                for k, v in obj.items()
                if v != SECRET_PLACEHOLDER
            }  # type: ignore
        if isinstance(obj, list):
            return [deep_remove(v) for v in obj]  # type: ignore
        if obj == SECRET_PLACEHOLDER:
            return None
        return obj

    return deep_remove(copy.deepcopy(config))  # type: ignore

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, TypeVar, cast

from marimo._config.config import MarimoConfig, PartialMarimoConfig
from marimo._config.utils import deep_copy

SECRET_PLACEHOLDER = "********"

# TODO: mypy doesn't like using @overload here


def mask_secrets_partial(config: PartialMarimoConfig) -> PartialMarimoConfig:
    return cast(PartialMarimoConfig, mask_secrets(cast(MarimoConfig, config)))


def mask_secrets(config: MarimoConfig) -> MarimoConfig:
    def deep_remove_from_path(path: list[str], obj: dict[str, Any]) -> None:
        if not path:
            return

        key = path[0]
        remaining_path = path[1:]

        if key == "*":
            for v in obj.values():
                if isinstance(v, dict):
                    deep_remove_from_path(remaining_path, v)
                elif isinstance(v, list) and remaining_path:
                    # Only first layer recursion
                    for item in v:
                        if isinstance(item, dict):
                            deep_remove_from_path(remaining_path, item)
            return
        if key not in obj:
            return
        if len(path) == 1:
            if isinstance(obj[key], list):
                obj[key] = []
            elif obj[key]:
                obj[key] = SECRET_PLACEHOLDER
        else:
            deep_remove_from_path(remaining_path, obj[key])

    secrets = (
        ("ai", "*", "api_key"),
        ("ai", "bedrock", "aws_access_key_id"),
        ("ai", "bedrock", "aws_secret_access_key"),
        ("runtime", "dotenv"),
    )

    new_config = deep_copy(config)
    config_dict = cast(dict[str, Any], new_config)

    for secret in secrets:
        deep_remove_from_path(list(secret), config_dict)

    return new_config  # type: ignore


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

    return deep_remove(deep_copy(config))  # type: ignore

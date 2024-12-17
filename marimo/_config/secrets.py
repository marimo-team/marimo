# Copyright 2024 Marimo. All rights reserved.
from typing import Any, Dict, TypeVar, Union, cast

from marimo._config.config import MarimoConfig, PartialMarimoConfig
from marimo._config.utils import deep_copy

SECRET_PLACEHOLDER = "********"


def mask_secrets(
    config: Union[MarimoConfig, PartialMarimoConfig],
) -> MarimoConfig:
    def deep_remove_from_path(path: list[str], obj: Dict[str, Any]) -> None:
        key = path[0]
        if key not in obj:
            return
        if len(path) == 1:
            if obj[key]:
                obj[key] = SECRET_PLACEHOLDER
        else:
            deep_remove_from_path(path[1:], cast(Dict[str, Any], obj[key]))

    secrets = [
        ["ai", "open_ai", "api_key"],
        ["ai", "anthropic", "api_key"],
        ["ai", "google", "api_key"],
    ]

    new_config = deep_copy(config)
    for secret in secrets:
        deep_remove_from_path(secret, cast(Dict[str, Any], new_config))

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

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import copy
import re
from typing import Any, TypeAlias

import msgspec

from marimo._config.config_schema import MarimoConfig
from marimo._utils.deep_merge import deep_merge

# Sparse external settings must not acquire defaults before layer resolution.
PartialMarimoConfig: TypeAlias = dict[str, Any]
DEFAULT_CONFIG = MarimoConfig()


def parse_config(values: PartialMarimoConfig) -> MarimoConfig:
    """Use schema defaults for invalid settings after reporting their source."""
    values = copy.deepcopy(values)
    while True:
        try:
            return MarimoConfig.from_dict(values)
        except msgspec.ValidationError as error:
            match = re.search(r" - at `\$(.*?)`$", str(error))
            if match is None:
                raise
            path = re.findall(r"\.([^.[\]]+)", match[1].split("[")[0])
            if not path:
                raise
            section = values
            for key in path[:-1]:
                section = section[key]
            if path == ["cache", "verification"]:
                section[path[-1]] = "on"
            else:
                del section[path[-1]]


def merge_default_config(
    config: PartialMarimoConfig | MarimoConfig,
) -> MarimoConfig:
    """Merge a user configuration with the default configuration."""
    return merge_config(DEFAULT_CONFIG, config)


def merge_config(
    config: MarimoConfig | PartialMarimoConfig,
    new_config: PartialMarimoConfig | MarimoConfig,
) -> MarimoConfig:
    """Merge a user configuration with a new configuration. The new config
    will take precedence over the default config.

    Args:
        config: The default configuration.
        new_config: The new configuration to merge with the default config.

    Returns:
        A merged configuration.
    """
    config_dict = (
        config.to_dict() if isinstance(config, MarimoConfig) else config
    )
    patch = (
        new_config.to_dict()
        if isinstance(new_config, MarimoConfig)
        else new_config
    )
    return MarimoConfig.from_dict(merge_config_dict(config_dict, patch))


def merge_config_dict(
    config: dict[str, Any], new_config: dict[str, Any]
) -> dict[str, Any]:
    # Remove the keymap overrides from the incoming config,
    # so that they don't get merged into the new config
    if new_config.get("keymap", {}).get("overrides") is not None:
        # Clone config to avoid modifying the original
        config = copy.deepcopy(config)
        config.get("keymap", {}).pop("overrides", {})

    # Fields that should be replaced instead of merged.
    # These are "record" types where keys can be added/removed,
    # as opposed to config objects where you only set specific fields.
    # NB. `signing.trusted_signers` is replaced, not deep-merged. A deep merge
    # unions the fingerprints from every layer. Then no layer can remove a
    # signer that a lower-priority one anchored.
    replace_paths = frozenset(
        {"ai.custom_providers", "signing.trusted_signers"}
    )

    merged = deep_merge(config, new_config, replace_paths=replace_paths)

    # Patches for backward compatibility
    if "runtime" in merged:
        if merged["runtime"].get("auto_reload") is False:
            merged["runtime"]["auto_reload"] = "off"
        elif (merged["runtime"].get("auto_reload") is True) or (
            merged["runtime"].get("auto_reload") == "detect"
        ):
            merged["runtime"]["auto_reload"] = "lazy"

    return merged

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from marimo._config.config import PartialMarimoConfig, merge_config_dict
from marimo._config.provenance import (
    ConfigLayer,
    ConfigPath,
    ResolvedConfig,
)
from marimo._config.utils import deep_copy

if TYPE_CHECKING:
    from collections.abc import Iterable


def merge_config_patches(
    patches: Iterable[PartialMarimoConfig],
) -> PartialMarimoConfig:
    """Merge sparse patches in order, with later patches taking precedence."""
    merged: PartialMarimoConfig = {}
    for patch in patches:
        merged = merge_config_dict(merged, deep_copy(patch))
    return deep_copy(merged)


def resolve_config(
    defaults: PartialMarimoConfig,
    patches: Iterable[PartialMarimoConfig],
    *,
    fallback: PartialMarimoConfig | None = None,
) -> PartialMarimoConfig:
    """Resolve defaults and ordered patches without reading or masking sources.

    Contextual fallback values fill gaps in the schema defaults. Explicit
    patches take precedence over both kinds of defaults.
    """
    config = merge_config_dict(deep_copy(fallback or {}), deep_copy(defaults))
    for patch in patches:
        config = merge_config_dict(config, deep_copy(patch))
    return config


def config_paths(
    config: dict[str, Any],
    path: ConfigPath = (),
    *,
    leaf_paths: frozenset[ConfigPath] = frozenset(),
) -> Iterable[ConfigPath]:
    """Yield leaf paths, treating lists and empty tables as single values."""
    for key, value in config.items():
        field_path = (*path, key)
        if isinstance(value, dict) and value and field_path not in leaf_paths:
            yield from config_paths(value, field_path, leaf_paths=leaf_paths)
        else:
            yield field_path


def resolve_config_with_sources(
    layers: Iterable[ConfigLayer],
) -> ResolvedConfig:
    """Track explicit writes while applying the normal configuration merge rules."""
    resolved = ResolvedConfig({}, {})
    for layer in layers:
        supplied = dict.fromkeys(config_paths(layer.config), layer.source)
        resolved = merge_resolved_configs(
            resolved,
            ResolvedConfig(layer.config, supplied),
        )
    return resolved


def merge_resolved_configs(
    base: ResolvedConfig, overrides: ResolvedConfig
) -> ResolvedConfig:
    """Merge resolved groups without losing their original field sources."""
    config = merge_config_dict(base.config, deep_copy(overrides.config))
    # Keep only surviving fields after record replacements and deletions.
    origins = {
        path: overrides.origins[path]
        if path in overrides.origins
        else base.origins[path]
        for path in config_paths(config)
    }
    return ResolvedConfig(config, origins)

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from marimo._config.config import (
    MarimoConfig,
    PartialMarimoConfig,
    merge_config,
)
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
    merged = cast(MarimoConfig, {})
    for patch in patches:
        merged = merge_config(merged, deep_copy(patch))
    return cast(PartialMarimoConfig, deep_copy(merged))


def resolve_config(
    defaults: MarimoConfig,
    patches: Iterable[PartialMarimoConfig],
    *,
    fallback: PartialMarimoConfig | None = None,
) -> MarimoConfig:
    """Resolve defaults and ordered patches without reading or masking sources.

    Contextual fallback values fill gaps in the schema defaults. Explicit
    patches take precedence over both kinds of defaults.
    """
    config = merge_config(
        cast(MarimoConfig, deep_copy(fallback or {})), deep_copy(defaults)
    )
    for patch in patches:
        config = merge_config(config, deep_copy(patch))
    return config


def config_paths(
    config: dict[str, Any], path: ConfigPath = ()
) -> Iterable[ConfigPath]:
    """Yield leaf paths, treating lists and empty tables as single values."""
    for key, value in config.items():
        field_path = (*path, key)
        if isinstance(value, dict) and value:
            yield from config_paths(value, field_path)
        else:
            yield field_path


def resolve_config_with_sources(
    layers: Iterable[ConfigLayer],
) -> ResolvedConfig:
    """Track explicit writes while applying the normal configuration merge rules."""
    resolved = ResolvedConfig(cast(MarimoConfig, {}), {})
    for layer in layers:
        supplied = dict.fromkeys(
            config_paths(cast(dict[str, Any], layer.config)), layer.source
        )
        resolved = merge_resolved_configs(
            resolved,
            ResolvedConfig(cast(MarimoConfig, layer.config), supplied),
        )
    return resolved


def merge_resolved_configs(
    base: ResolvedConfig, overrides: ResolvedConfig
) -> ResolvedConfig:
    """Merge resolved groups without losing their original field sources."""
    config = merge_config(base.config, deep_copy(overrides.config))
    # Keep only surviving fields after record replacements and deletions.
    origins = {
        path: overrides.origins[path]
        if path in overrides.origins
        else base.origins[path]
        for path in config_paths(cast(dict[str, Any], config))
    }
    return ResolvedConfig(config, origins)

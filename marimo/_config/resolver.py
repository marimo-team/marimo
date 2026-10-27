# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from marimo._config.config import (
    MarimoConfig,
    PartialMarimoConfig,
    merge_config,
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

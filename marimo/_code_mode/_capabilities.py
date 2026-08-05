# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._entrypoints.ids import KnownEntryPoint
from marimo._entrypoints.registry import get_entry_points

_ENTRY_POINT_GROUP: KnownEntryPoint = "marimo.agent.capability"


def capabilities() -> dict[str, str]:
    """Return installed capability names mapped to importable modules."""
    modules: dict[str, str] = {}
    for entry_point in get_entry_points(_ENTRY_POINT_GROUP):
        module = entry_point.module
        registered = modules.get(entry_point.name)
        if registered is not None and registered != module:
            raise RuntimeError(
                f"Multiple capability modules are registered as "
                f"{entry_point.name!r}"
            )
        modules[entry_point.name] = module
    return dict(sorted(modules.items()))

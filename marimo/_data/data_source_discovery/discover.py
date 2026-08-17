# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._data.data_source_discovery.models import DetectedDataSource
from marimo._data.data_source_discovery.plugins import (
    DEFAULT_DISCOVERY_PLUGINS,
)
from marimo._data.data_source_discovery.types import (
    DiscoveryContext,
    DiscoveryPlugin,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

LOGGER = _loggers.marimo_logger()


def discover_data_sources(
    environment: Mapping[str, str],
    plugins: Sequence[DiscoveryPlugin] = DEFAULT_DISCOVERY_PLUGINS,
) -> list[DetectedDataSource]:
    """Run isolated detectors without exposing secret values to the frontend."""
    # Give every plugin the same immutable snapshot. A detector cannot mutate
    # the live process environment or affect a detector that runs after it.
    context = DiscoveryContext(environment=MappingProxyType(dict(environment)))
    sources: list[DetectedDataSource] = []

    for plugin in plugins:
        try:
            sources.extend(plugin.discover(context))
        except Exception as exc:
            LOGGER.warning(
                "Datasource discovery plugin %s failed (%s)",
                plugin.id,
                type(exc).__name__,
            )

    seen: set[str] = set()
    unique_sources: list[DetectedDataSource] = []
    for source in sources:
        if source.id not in seen:
            seen.add(source.id)
            unique_sources.append(source)
    return unique_sources

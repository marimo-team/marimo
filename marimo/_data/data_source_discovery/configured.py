# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from marimo._data.data_source_discovery.models import DetectedDataSource
from marimo._data.data_source_discovery.types import (
    DiscoveryNamespaceContext,
    DiscoveryPlugin,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = [
    "DiscoveryNamespaceContext",
    "annotate_configured_sources",
    "is_data_source_already_configured",
]


def is_data_source_already_configured(
    source: DetectedDataSource,
    namespace: DiscoveryNamespaceContext,
    plugins: Sequence[DiscoveryPlugin] | None = None,
) -> bool:
    """Whether a detected source is already backed by a live connection."""
    return _is_configured(source, namespace, _plugin_by_id(plugins))


def annotate_configured_sources(
    sources: list[DetectedDataSource],
    namespace: DiscoveryNamespaceContext,
    plugins: Sequence[DiscoveryPlugin] | None = None,
) -> list[DetectedDataSource]:
    plugin_by_id = _plugin_by_id(plugins)
    return [
        msgspec.structs.replace(
            source,
            configured=_is_configured(source, namespace, plugin_by_id),
        )
        for source in sources
    ]


def _is_configured(
    source: DetectedDataSource,
    namespace: DiscoveryNamespaceContext,
    plugin_by_id: Mapping[str, DiscoveryPlugin],
) -> bool:
    plugin = plugin_by_id.get(source.integration)
    if plugin is None:
        return False
    return plugin.configured_when.matches(namespace)


def _plugin_by_id(
    plugins: Sequence[DiscoveryPlugin] | None,
) -> dict[str, DiscoveryPlugin]:
    if plugins is None:
        from marimo._data.data_source_discovery.plugins import (
            DEFAULT_DISCOVERY_PLUGINS,
        )

        plugins = DEFAULT_DISCOVERY_PLUGINS
    return {plugin.id: plugin for plugin in plugins}

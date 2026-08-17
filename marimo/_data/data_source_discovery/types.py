# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from marimo._data.data_source_discovery.models import DetectedDataSource

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence


@dataclass(frozen=True)
class DiscoveryContext:
    """Kernel-local inputs available to datasource discovery plugins."""

    environment: Mapping[str, str]


@dataclass(frozen=True)
class DiscoveryNamespaceContext:
    """Live notebook namespace used to hide redundant quick-add suggestions."""

    dialects: tuple[str, ...]
    storage_protocols: tuple[str, ...]
    storage_backend_types: tuple[str, ...]


@dataclass(frozen=True)
class DialectMatch:
    """Match live SQL engines whose dialect contains any of these substrings."""

    substrings: tuple[str, ...] = ()

    def matches(self, namespace: DiscoveryNamespaceContext) -> bool:
        if not self.substrings:
            return False
        return any(
            any(alias in dialect for alias in self.substrings)
            for dialect in namespace.dialects
        )


@dataclass(frozen=True)
class StorageMatch:
    """Match live storage namespaces by protocol and/or backend type."""

    protocols: tuple[str, ...] = ()
    backend_types: tuple[str, ...] = ()

    def matches(self, namespace: DiscoveryNamespaceContext) -> bool:
        if any(
            protocol in namespace.storage_protocols
            for protocol in self.protocols
        ):
            return True
        return any(
            backend_type in namespace.storage_backend_types
            for backend_type in self.backend_types
        )


ConfiguredMatch = DialectMatch | StorageMatch


@dataclass(frozen=True)
class DiscoveryPlugin:
    """A self-contained, independently testable datasource detector."""

    id: str
    discover: Callable[
        [DiscoveryContext],
        Sequence[DetectedDataSource],
    ]
    configured_when: ConfiguredMatch

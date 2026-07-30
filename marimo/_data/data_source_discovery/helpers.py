# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._data.data_source_discovery.models import (
    DetectedDataSourceConfiguration,
    DetectedDataSourceOrigin,
    EnvironmentVariableDiscoveryValue,
    SafeLiteralDiscoveryValue,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

ENVIRONMENT_ORIGIN = DetectedDataSourceOrigin(
    type="environment",
    label="Kernel environment",
)
RESOLVED_CONFIGURATION_ORIGIN = DetectedDataSourceOrigin(
    type="configuration",
    label="Resolved PyIceberg configuration",
)


def has_value(environment: Mapping[str, str], name: str) -> bool:
    """Return whether an environment variable has a non-empty value."""
    return bool(environment.get(name))


def has_all(environment: Mapping[str, str], names: tuple[str, ...]) -> bool:
    return all(has_value(environment, name) for name in names)


def is_valid_port(value: str | None) -> bool:
    """Return whether a value is a valid integer network port."""
    if value is None:
        return False
    try:
        port = int(value)
    except ValueError:
        return False
    return 1 <= port <= 65535


def environment_variable(
    field: str, name: str
) -> DetectedDataSourceConfiguration:
    return DetectedDataSourceConfiguration(
        field=field,
        value=EnvironmentVariableDiscoveryValue(name=name),
    )


def safe_literal(field: str, value: str) -> DetectedDataSourceConfiguration:
    return DetectedDataSourceConfiguration(
        field=field,
        value=SafeLiteralDiscoveryValue(value=value),
    )

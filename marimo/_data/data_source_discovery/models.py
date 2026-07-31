# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

import msgspec

DataSourceCategory = Literal["database", "catalog", "object-storage"]
DataSourceConfidence = Literal["high", "medium"]
DataSourceDiscoveryOriginKind = Literal["environment", "configuration"]


class EnvironmentVariableDiscoveryValue(
    msgspec.Struct,
    frozen=True,
    tag="environment-variable",
    tag_field="kind",
    rename="camel",
):
    """A reference to an environment variable, never its value."""

    name: str


class SafeLiteralDiscoveryValue(
    msgspec.Struct,
    frozen=True,
    tag="safe-literal",
    tag_field="kind",
    rename="camel",
):
    """Non-sensitive metadata that is safe to send to the frontend."""

    value: str


DataSourceDiscoveryValue = (
    EnvironmentVariableDiscoveryValue | SafeLiteralDiscoveryValue
)


class DetectedDataSourceConfiguration(
    msgspec.Struct, frozen=True, rename="camel"
):
    field: str
    value: DataSourceDiscoveryValue


class DetectedDataSourceOrigin(msgspec.Struct, frozen=True, rename="camel"):
    type: DataSourceDiscoveryOriginKind
    label: str


class DetectedDataSource(msgspec.Struct, frozen=True, rename="camel"):
    """A secret-free datasource suggestion produced by the kernel."""

    id: str
    integration: str
    category: DataSourceCategory
    display_name: str
    confidence: DataSourceConfidence
    origins: tuple[DetectedDataSourceOrigin, ...]
    configuration: tuple[DetectedDataSourceConfiguration, ...]
    code: str

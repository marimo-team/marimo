# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

import yaml

from marimo import _loggers
from marimo._data.data_source_discovery.helpers import (
    ENVIRONMENT_ORIGIN,
    RESOLVED_CONFIGURATION_ORIGIN,
    environment_variable,
    safe_literal,
)
from marimo._data.data_source_discovery.models import (
    DetectedDataSource,
    DetectedDataSourceConfiguration,
    DetectedDataSourceOrigin,
)
from marimo._data.data_source_discovery.types import (
    DiscoveryContext,
    DiscoveryPlugin,
)
from marimo._dependencies.dependencies import DependencyManager

CATALOG_PREFIX = "PYICEBERG_CATALOG__"
CONFIDENCE_PROPERTIES = frozenset({"py-catalog-impl", "type", "uri"})
CONFIG_FILENAME = ".pyiceberg.yaml"
CATALOG_TYPE_LABELS = {
    "rest": "REST",
    "hive": "Hive",
    "glue": "Glue",
    "dynamodb": "DynamoDB",
    "sql": "SQL",
    "in-memory": "In-memory",
    "bigquery": "BigQuery",
}

CatalogConfiguration = Mapping[str, object]
CatalogConfigurations = Mapping[str, CatalogConfiguration]
CatalogConfigurationLoader = Callable[[], CatalogConfigurations]
LOGGER = _loggers.marimo_logger()


def discover(
    context: DiscoveryContext,
    load_catalogs: CatalogConfigurationLoader | None = None,
) -> list[DetectedDataSource]:
    environment_sources = _detect_environment_catalogs(context.environment)
    try:
        catalogs = (
            load_catalogs()
            if load_catalogs is not None
            else _load_resolved_catalogs(environment=context.environment)
        )
        resolved_sources = _detect_resolved_catalogs(catalogs)
    except Exception as exc:
        LOGGER.warning(
            "PyIceberg resolved configuration discovery failed (%s)",
            type(exc).__name__,
        )
        resolved_sources = []
    return _merge_catalogs([*environment_sources, *resolved_sources])


def _detect_environment_catalogs(
    environment: Mapping[str, str],
) -> list[DetectedDataSource]:
    catalogs: dict[str, list[tuple[str, str]]] = {}

    for variable_name, value in environment.items():
        if not value:
            continue
        if not variable_name.startswith(CATALOG_PREFIX):
            continue

        remainder = variable_name[len(CATALOG_PREFIX) :]
        catalog_name, separator, property_name = remainder.partition("__")
        if not separator:
            continue

        catalog_name = _normalize_key(catalog_name)
        property_name = _normalize_key(property_name)
        if not catalog_name or not property_name:
            continue

        catalogs.setdefault(catalog_name, []).append(
            (property_name, variable_name)
        )

    sources: list[DetectedDataSource] = []
    for catalog_name, properties in sorted(catalogs.items()):
        if not any(
            property_name in CONFIDENCE_PROPERTIES
            for property_name, _ in properties
        ):
            continue

        configuration = [safe_literal("Catalog", catalog_name)]
        configuration.extend(
            environment_variable(property_name, variable_name)
            for property_name, variable_name in sorted(
                properties, key=lambda item: item[1]
            )
        )
        sources.append(
            _iceberg_source(
                catalog_name=catalog_name,
                origins=(ENVIRONMENT_ORIGIN,),
                configuration=configuration,
            )
        )
    return sources


def _detect_resolved_catalogs(
    catalogs: CatalogConfigurations,
) -> list[DetectedDataSource]:
    sources: list[DetectedDataSource] = []
    for catalog_name, configuration in sorted(catalogs.items()):
        if not catalog_name:
            continue
        catalog_type = _infer_catalog_type(configuration)
        if catalog_type is None:
            continue
        sources.append(
            _iceberg_source(
                catalog_name=catalog_name,
                origins=(RESOLVED_CONFIGURATION_ORIGIN,),
                configuration=[
                    safe_literal("Catalog", catalog_name),
                    safe_literal("Type", catalog_type),
                ],
            )
        )
    return sources


def _load_resolved_catalogs(
    *,
    environment: Mapping[str, str] | None = None,
    home_directory: Path | None = None,
    current_directory: Path | None = None,
) -> CatalogConfigurations:
    """Resolve catalogs with the same PyIceberg configuration used at runtime."""
    # PyIceberg's `Config` reads the live process environment directly. Only
    # use it when the caller has not supplied an environment snapshot.
    if environment is None and DependencyManager.pyiceberg.has(quiet=True):
        from pyiceberg.utils.config import Config

        config = Config()
        return {
            name: cast(
                CatalogConfiguration, config.get_catalog_config(name) or {}
            )
            for name in config.get_known_catalogs()
        }

    catalogs = _load_catalogs_from_configuration_file(
        environment=os.environ if environment is None else environment,
        home_directory=Path.home()
        if home_directory is None
        else home_directory,
        current_directory=Path.cwd()
        if current_directory is None
        else current_directory,
    )
    return _apply_environment_catalog_overrides(
        catalogs,
        os.environ if environment is None else environment,
    )


def _load_catalogs_from_configuration_file(
    *,
    environment: Mapping[str, str],
    home_directory: Path,
    current_directory: Path,
) -> CatalogConfigurations:
    """Load the first `.pyiceberg.yaml` using PyIceberg's search order."""
    search_directories = [
        Path(configured_home)
        for configured_home in [environment.get("PYICEBERG_HOME")]
        if configured_home
    ]
    search_directories.extend((home_directory, current_directory))

    for directory in search_directories:
        path = directory / CONFIG_FILENAME
        if not path.is_file():
            continue

        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        if config is None:
            continue
        if not config:
            continue
        return _catalogs_from_file_config(_lowercase_keys(config))

    return {}


def _apply_environment_catalog_overrides(
    catalogs: CatalogConfigurations,
    environment: Mapping[str, str],
) -> CatalogConfigurations:
    """Apply environment metadata to catalogs resolved from a config file."""
    merged = {
        name: dict(configuration) for name, configuration in catalogs.items()
    }

    for variable_name, value in environment.items():
        if not variable_name.startswith(CATALOG_PREFIX):
            continue

        remainder = variable_name[len(CATALOG_PREFIX) :]
        catalog_name, separator, property_name = remainder.partition("__")
        if not separator:
            continue

        catalog_name = _normalize_key(catalog_name)
        property_name = _normalize_key(property_name)
        if (
            catalog_name not in merged
            or property_name not in CONFIDENCE_PROPERTIES
        ):
            continue
        merged[catalog_name][property_name] = value

    return merged


def _lowercase_keys(value: object) -> object:
    if isinstance(value, dict):
        lowered: dict[str, object] = {}
        for key, nested_value in value.items():
            if not isinstance(key, str):
                raise TypeError("PyIceberg configuration keys must be strings")
            lowered[key.lower()] = _lowercase_keys(nested_value)
        return lowered
    if isinstance(value, list):
        return [_lowercase_keys(item) for item in value]
    return value


def _catalogs_from_file_config(config: object) -> CatalogConfigurations:
    if not isinstance(config, Mapping):
        raise TypeError("PyIceberg configuration must be an object")

    catalogs = config.get("catalog", {})
    if not isinstance(catalogs, Mapping):
        raise TypeError("PyIceberg catalog configuration must be an object")

    result: dict[str, CatalogConfiguration] = {}
    for name, catalog_config in catalogs.items():
        if not isinstance(name, str) or not isinstance(
            catalog_config, Mapping
        ):
            raise TypeError(
                "PyIceberg catalog entries must map names to objects"
            )
        result[name] = cast(CatalogConfiguration, catalog_config)
    return result


def _iceberg_source(
    *,
    catalog_name: str,
    origins: tuple[DetectedDataSourceOrigin, ...],
    configuration: Sequence[DetectedDataSourceConfiguration],
) -> DetectedDataSource:
    return DetectedDataSource(
        id=f"pyiceberg-{catalog_name}",
        integration="pyiceberg",
        category="catalog",
        display_name=f"PyIceberg ({catalog_name})",
        confidence="high",
        origins=origins,
        configuration=tuple(configuration),
        code="\n".join(
            [
                "from pyiceberg.catalog import load_catalog",
                "",
                f"catalog = load_catalog({json.dumps(catalog_name)})",
            ]
        ),
    )


def _merge_catalogs(
    sources: list[DetectedDataSource],
) -> list[DetectedDataSource]:
    by_id: dict[str, DetectedDataSource] = {}

    for source in sources:
        existing = by_id.get(source.id)
        if existing is None:
            by_id[source.id] = source
            continue

        by_id[source.id] = DetectedDataSource(
            id=existing.id,
            integration=existing.integration,
            category=existing.category,
            display_name=existing.display_name,
            confidence=existing.confidence,
            origins=tuple(dict.fromkeys((*existing.origins, *source.origins))),
            configuration=tuple(
                dict.fromkeys((*existing.configuration, *source.configuration))
            ),
            code=existing.code,
        )

    return list(by_id.values())


def _normalize_key(value: str) -> str:
    return value.lower().replace("__", ".").replace("_", "-")


def _infer_catalog_type(
    configuration: CatalogConfiguration,
) -> str | None:
    explicit_type = configuration.get("type")
    if isinstance(explicit_type, str) and explicit_type.strip():
        return _format_catalog_type(explicit_type)

    catalog_impl = configuration.get("py-catalog-impl")
    if isinstance(catalog_impl, str) and catalog_impl.strip():
        return "Custom"

    uri = configuration.get("uri")
    if not isinstance(uri, str) or not uri.strip():
        return None
    normalized_uri = uri.lower()
    if normalized_uri.startswith(("http://", "https://")):
        return "REST"
    if normalized_uri.startswith("thrift://"):
        return "Hive"
    if normalized_uri.startswith(("sqlite:", "postgresql")):
        return "SQL"
    return None


def _format_catalog_type(value: str) -> str | None:
    return CATALOG_TYPE_LABELS.get(value.strip().lower())


PYICEBERG_PLUGIN = DiscoveryPlugin(id="pyiceberg", discover=discover)

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import msgspec
from inline_snapshot import snapshot

from marimo._data.data_source_discovery.models import (
    SafeLiteralDiscoveryValue,
)
from marimo._data.data_source_discovery.plugins.pyiceberg import (
    _load_resolved_catalogs,
    discover,
)
from marimo._data.data_source_discovery.types import DiscoveryContext

if TYPE_CHECKING:
    from pathlib import Path


def test_merges_environment_with_resolved_configuration() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "PYICEBERG_CATALOG__PROD__URI": "https://secret.invalid",
                "PYICEBERG_CATALOG__PROD__WAREHOUSE": "s3://secret",
            }
        ),
        load_catalogs=lambda: {
            "hive": {
                "uri": "thrift://secret-host:9083",
                "credential": "do-not-copy",
            },
            "prod": {
                "type": "rest",
                "credential": "do-not-copy",
            },
        },
    )

    builtins = msgspec.json.decode(msgspec.json.encode(detected))
    assert builtins == snapshot(
        [
            {
                "id": "pyiceberg-prod",
                "integration": "pyiceberg",
                "category": "catalog",
                "displayName": "PyIceberg (prod)",
                "confidence": "high",
                "origins": [
                    {
                        "type": "environment",
                        "label": "Kernel environment",
                    },
                    {
                        "type": "configuration",
                        "label": "Resolved PyIceberg configuration",
                    },
                ],
                "configuration": [
                    {
                        "field": "Catalog",
                        "value": {
                            "kind": "safe-literal",
                            "value": "prod",
                        },
                    },
                    {
                        "field": "uri",
                        "value": {
                            "kind": "environment-variable",
                            "name": "PYICEBERG_CATALOG__PROD__URI",
                        },
                    },
                    {
                        "field": "warehouse",
                        "value": {
                            "kind": "environment-variable",
                            "name": "PYICEBERG_CATALOG__PROD__WAREHOUSE",
                        },
                    },
                    {
                        "field": "Type",
                        "value": {
                            "kind": "safe-literal",
                            "value": "REST",
                        },
                    },
                ],
                "code": """\
from pyiceberg.catalog import load_catalog

catalog = load_catalog("prod")""",
            },
            {
                "id": "pyiceberg-hive",
                "integration": "pyiceberg",
                "category": "catalog",
                "displayName": "PyIceberg (hive)",
                "confidence": "high",
                "origins": [
                    {
                        "type": "configuration",
                        "label": "Resolved PyIceberg configuration",
                    }
                ],
                "configuration": [
                    {
                        "field": "Catalog",
                        "value": {
                            "kind": "safe-literal",
                            "value": "hive",
                        },
                    },
                    {
                        "field": "Type",
                        "value": {
                            "kind": "safe-literal",
                            "value": "Hive",
                        },
                    },
                ],
                "code": """\
from pyiceberg.catalog import load_catalog

catalog = load_catalog("hive")""",
            },
        ]
    )
    assert "do-not-copy" not in repr(builtins)
    assert "secret" not in repr(builtins)


def test_ignores_low_confidence_catalogs() -> None:
    detected = discover(
        DiscoveryContext(
            environment={"PYICEBERG_CATALOG__PROD__WAREHOUSE": "s3://secret"}
        ),
        load_catalogs=lambda: {"prod": {"credential": "do-not-copy"}},
    )

    assert detected == snapshot([])


def test_resolved_configuration_failure_preserves_environment_catalogs() -> (
    None
):
    sentinel = "TOP-SECRET-CONFIGURATION"

    def fail() -> dict[str, dict[str, str]]:
        raise ValueError(sentinel)

    with patch(
        "marimo._data.data_source_discovery.plugins.pyiceberg.LOGGER.warning"
    ) as log_warning:
        detected = discover(
            DiscoveryContext(
                environment={
                    "PYICEBERG_CATALOG__PROD__URI": ("https://secret.invalid")
                }
            ),
            load_catalogs=fail,
        )

    payload = msgspec.json.encode(detected).decode()
    assert [source.id for source in detected] == snapshot(["pyiceberg-prod"])
    assert sentinel not in payload
    log_warning.assert_called_once_with(
        "PyIceberg resolved configuration discovery failed (%s)",
        "ValueError",
    )
    assert sentinel not in repr(log_warning.call_args_list)


def test_rejects_unknown_explicit_catalog_type_without_leaking_it() -> None:
    sentinel = "TOP-SECRET-TOKEN"
    detected = discover(
        DiscoveryContext(environment={}),
        load_catalogs=lambda: {
            "unknown": {
                "type": sentinel,
                "uri": "https://catalog.invalid",
            }
        },
    )

    payload = msgspec.json.encode(detected).decode()
    assert detected == snapshot([])
    assert sentinel.casefold() not in payload.casefold()


def test_ignores_empty_and_malformed_environment_catalogs() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "PYICEBERG_CATALOG__PROD__URI": "",
                "PYICEBERG_CATALOG____URI": "https://secret.invalid",
                "PYICEBERG_CATALOG__MISSING_PROPERTY": "secret",
                "PYICEBERG_CATALOG__LOW__WAREHOUSE": "s3://secret",
            }
        ),
        load_catalogs=dict,
    )

    assert detected == snapshot([])


def test_resolved_catalog_type_inference_and_name_escaping() -> None:
    detected = discover(
        DiscoveryContext(environment={}),
        load_catalogs=lambda: {
            "blank": {
                "type": " ",
                "uri": "",
                "py-catalog-impl": object(),
            },
            'quoted"name': {
                "type": " REST ",
                "credential": "do-not-copy",
            },
            "sql": {"uri": "POSTGRESQL://secret.invalid/database"},
            "custom": {"py-catalog-impl": "package.CustomCatalog"},
        },
    )

    detected_types: list[tuple[str, str]] = []
    for source in detected:
        value = source.configuration[-1].value
        assert isinstance(value, SafeLiteralDiscoveryValue)
        detected_types.append((source.id, value.value))

    assert detected_types == snapshot(
        [
            ("pyiceberg-custom", "Custom"),
            ('pyiceberg-quoted"name', "REST"),
            ("pyiceberg-sql", "SQL"),
        ]
    )
    for source in detected:
        ast.parse(source.code)
    assert 'load_catalog("quoted\\"name")' in detected[1].code
    assert "do-not-copy" not in repr(detected)
    assert "secret.invalid" not in repr(detected)


def test_supports_known_explicit_catalog_types() -> None:
    detected = discover(
        DiscoveryContext(environment={}),
        load_catalogs=lambda: {
            catalog_type: {"type": catalog_type}
            for catalog_type in (
                "rest",
                "hive",
                "glue",
                "dynamodb",
                "sql",
                "in-memory",
                "bigquery",
            )
        },
    )

    detected_types: list[tuple[str, str]] = []
    for source in detected:
        value = source.configuration[-1].value
        assert isinstance(value, SafeLiteralDiscoveryValue)
        detected_types.append((source.id, value.value))

    assert detected_types == snapshot(
        [
            ("pyiceberg-bigquery", "BigQuery"),
            ("pyiceberg-dynamodb", "DynamoDB"),
            ("pyiceberg-glue", "Glue"),
            ("pyiceberg-hive", "Hive"),
            ("pyiceberg-in-memory", "In-memory"),
            ("pyiceberg-rest", "REST"),
            ("pyiceberg-sql", "SQL"),
        ]
    )


def test_configuration_file_search_precedence(tmp_path: Path) -> None:
    configured_home = tmp_path / "configured"
    home_directory = tmp_path / "home"
    current_directory = tmp_path / "cwd"
    missing_home = tmp_path / "missing-home"
    for directory in (
        configured_home,
        home_directory,
        current_directory,
        missing_home,
    ):
        directory.mkdir()

    (configured_home / ".pyiceberg.yaml").write_text(
        """\
CATALOG:
  configured:
    TYPE: REST
    TOKEN: TOP-SECRET-CONFIGURED
""",
        encoding="utf-8",
    )
    (home_directory / ".pyiceberg.yaml").write_text(
        """\
catalog:
  home:
    uri: thrift://TOP-SECRET-HOME
""",
        encoding="utf-8",
    )
    (current_directory / ".pyiceberg.yaml").write_text(
        """\
catalog:
  current:
    type: sql
    credential: TOP-SECRET-CURRENT
""",
        encoding="utf-8",
    )

    with patch(
        "marimo._data.data_source_discovery.plugins.pyiceberg."
        "DependencyManager.pyiceberg.has",
        return_value=False,
    ):
        from_configured_home = _load_resolved_catalogs(
            environment={"PYICEBERG_HOME": str(configured_home)},
            home_directory=home_directory,
            current_directory=current_directory,
        )
        from_home = _load_resolved_catalogs(
            environment={},
            home_directory=home_directory,
            current_directory=current_directory,
        )
        from_current_directory = _load_resolved_catalogs(
            environment={},
            home_directory=missing_home,
            current_directory=current_directory,
        )

    assert {
        "configured": list(from_configured_home),
        "home": list(from_home),
        "current": list(from_current_directory),
    } == snapshot(
        {
            "configured": ["configured"],
            "home": ["home"],
            "current": ["current"],
        }
    )

    detected = discover(
        DiscoveryContext(environment={}),
        load_catalogs=lambda: from_configured_home,
    )
    payload = msgspec.json.encode(detected).decode()
    assert "TOP-SECRET-CONFIGURED" not in payload
    assert detected[0].display_name == snapshot("PyIceberg (configured)")


def test_discovery_uses_the_context_environment_snapshot(
    tmp_path: Path,
) -> None:
    context_home = tmp_path / "context"
    process_home = tmp_path / "process"
    context_home.mkdir()
    process_home.mkdir()
    (context_home / ".pyiceberg.yaml").write_text(
        "catalog:\n  snapshot:\n    type: rest\n",
        encoding="utf-8",
    )
    (process_home / ".pyiceberg.yaml").write_text(
        "catalog:\n  live-process:\n    type: hive\n",
        encoding="utf-8",
    )

    with (
        patch.dict(
            os.environ,
            {"PYICEBERG_HOME": str(process_home)},
            clear=True,
        ),
        patch(
            "marimo._data.data_source_discovery.plugins.pyiceberg."
            "DependencyManager.pyiceberg.has",
            return_value=True,
        ) as has_pyiceberg,
    ):
        detected = discover(
            DiscoveryContext(environment={"PYICEBERG_HOME": str(context_home)})
        )

    assert [source.id for source in detected] == snapshot(
        ["pyiceberg-snapshot"]
    )
    has_pyiceberg.assert_not_called()


def test_context_environment_overrides_file_catalog_metadata(
    tmp_path: Path,
) -> None:
    configured_home = tmp_path / "configured"
    configured_home.mkdir()
    (configured_home / ".pyiceberg.yaml").write_text(
        "catalog:\n  prod:\n    type: rest\n",
        encoding="utf-8",
    )

    detected = discover(
        DiscoveryContext(
            environment={
                "PYICEBERG_HOME": str(configured_home),
                "PYICEBERG_CATALOG__PROD__TYPE": "glue",
            }
        )
    )

    resolved_types: list[str] = []
    for configuration in detected[0].configuration:
        if configuration.field != "Type":
            continue
        value = configuration.value
        assert isinstance(value, SafeLiteralDiscoveryValue)
        resolved_types.append(value.value)

    assert [source.id for source in detected] == snapshot(["pyiceberg-prod"])
    assert resolved_types == snapshot(["Glue"])


def test_empty_configuration_falls_through_to_next_location(
    tmp_path: Path,
) -> None:
    configured_home = tmp_path / "configured"
    home_directory = tmp_path / "home"
    current_directory = tmp_path / "cwd"
    for directory in (configured_home, home_directory, current_directory):
        directory.mkdir()

    (configured_home / ".pyiceberg.yaml").write_text(
        "# intentionally empty\n",
        encoding="utf-8",
    )
    (home_directory / ".pyiceberg.yaml").write_text(
        "catalog:\n  home:\n    type: rest\n",
        encoding="utf-8",
    )

    with patch(
        "marimo._data.data_source_discovery.plugins.pyiceberg."
        "DependencyManager.pyiceberg.has",
        return_value=False,
    ):
        catalogs = _load_resolved_catalogs(
            environment={"PYICEBERG_HOME": str(configured_home)},
            home_directory=home_directory,
            current_directory=current_directory,
        )

    assert list(catalogs) == snapshot(["home"])

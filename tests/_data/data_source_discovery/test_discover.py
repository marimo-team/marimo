# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import logging
from io import StringIO
from unittest.mock import patch

import msgspec
from inline_snapshot import snapshot

from marimo._data.data_source_discovery import discover_data_sources
from marimo._data.data_source_discovery.discover import LOGGER
from marimo._data.data_source_discovery.helpers import (
    ENVIRONMENT_ORIGIN,
    hides_when_dialect,
)
from marimo._data.data_source_discovery.models import DetectedDataSource
from marimo._data.data_source_discovery.types import (
    DiscoveryContext,
    DiscoveryPlugin,
)


def test_isolates_failures_and_deduplicates() -> None:
    source = DetectedDataSource(
        id="shared",
        integration="example",
        category="database",
        display_name="Shared",
        confidence="high",
        origins=(ENVIRONMENT_ORIGIN,),
        configuration=(),
        code="connection = shared()",
        hides_when=hides_when_dialect("example"),
    )
    duplicate = DetectedDataSource(
        id="shared",
        integration="replacement",
        category="database",
        display_name="Replacement",
        confidence="high",
        origins=(ENVIRONMENT_ORIGIN,),
        configuration=(),
        code="connection = replacement()",
        hides_when=hides_when_dialect("example"),
    )

    def fail(_context: DiscoveryContext) -> list[DetectedDataSource]:
        raise RuntimeError("broken detector")

    with patch(
        "marimo._data.data_source_discovery.discover.LOGGER.warning"
    ) as log_warning:
        detected = discover_data_sources(
            {},
            plugins=(
                DiscoveryPlugin(
                    id="first", discover=lambda _context: [source]
                ),
                DiscoveryPlugin(
                    id="duplicate", discover=lambda _context: [duplicate]
                ),
                DiscoveryPlugin(id="broken", discover=fail),
            ),
        )

    assert detected == snapshot([source])
    log_warning.assert_called_once_with(
        "Datasource discovery plugin %s failed (%s)",
        "broken",
        "RuntimeError",
    )


def test_default_plugins_emit_valid_secret_free_suggestions() -> None:
    environment = {
        "PGHOST": "secret-pg-host",
        "PGPORT": "61231",
        "PGUSER": "secret-pg-user",
        "PGPASSWORD": "secret-pg-password",
        "PGDATABASE": "secret-pg-database",
        "MYSQL_HOST": "secret-mysql-host",
        "MYSQL_TCP_PORT": "61232",
        "MYSQL_USER": "secret-mysql-user",
        "MYSQL_PWD": "secret-mysql-password",
        "MYSQL_DATABASE": "secret-mysql-database",
        "AWS_PROFILE": "secret-aws-profile",
        "TRINO_HOST": "secret-trino-host",
        "TRINO_PORT": "61233",
        "TRINO_USER": "secret-trino-user",
        "TRINO_PASSWORD": "secret-trino-password",
        "TRINO_CATALOG": "secret-trino-catalog",
        "TRINO_SCHEMA": "secret-trino-schema",
        "DATABRICKS_SQL_WAREHOUSE_ID": "secret-databricks-warehouse",
        "DATABRICKS_CONFIG_PROFILE": "secret-databricks-profile",
        "SPARK_REMOTE": "sc://secret-spark-host:61234",
        "PYICEBERG_CATALOG__PROD__URI": "https://secret-iceberg.invalid",
    }

    with patch(
        "marimo._data.data_source_discovery.plugins.pyiceberg."
        "_load_resolved_catalogs",
        return_value={
            "resolved": {
                "type": "rest",
                "credential": "secret-resolved-credential",
            }
        },
    ):
        detected = discover_data_sources(environment)

    assert [source.integration for source in detected] == snapshot(
        [
            "postgres",
            "mysql",
            "aws",
            "trino",
            "databricks",
            "pyspark",
            "pyiceberg",
            "pyiceberg",
        ]
    )
    payload = msgspec.json.encode(detected).decode()
    for value in environment.values():
        assert value not in payload
    assert "secret-resolved-credential" not in payload
    for source in detected:
        ast.parse(source.code)


def test_plugins_receive_an_immutable_environment_snapshot() -> None:
    observed: list[str] = []

    def mutate(context: DiscoveryContext) -> list[DetectedDataSource]:
        context.environment["INJECTED"] = "value"  # type: ignore[index]
        return []

    def observe(context: DiscoveryContext) -> list[DetectedDataSource]:
        observed.extend(context.environment)
        return []

    with patch(
        "marimo._data.data_source_discovery.discover.LOGGER.warning"
    ) as log_warning:
        discover_data_sources(
            {"ORIGINAL": "value"},
            plugins=(
                DiscoveryPlugin(id="mutating", discover=mutate),
                DiscoveryPlugin(id="observing", discover=observe),
            ),
        )

    assert observed == snapshot(["ORIGINAL"])
    log_warning.assert_called_once_with(
        "Datasource discovery plugin %s failed (%s)",
        "mutating",
        "TypeError",
    )


def test_plugin_error_logs_never_include_exception_message() -> None:
    secret = "TOP-SECRET-URI"

    def fail(_context: DiscoveryContext) -> list[DetectedDataSource]:
        raise ValueError(
            "Incompatible configurations, merging dict with a value: "
            f"uri, value: {secret}"
        )

    log_output = StringIO()
    handler = logging.StreamHandler(log_output)
    LOGGER.addHandler(handler)
    try:
        detected = discover_data_sources(
            {},
            plugins=(DiscoveryPlugin(id="pyiceberg", discover=fail),),
        )
    finally:
        LOGGER.removeHandler(handler)
    logs = log_output.getvalue()

    assert detected == snapshot([])
    assert secret not in logs
    assert "ValueError" in logs
    assert "pyiceberg" in logs

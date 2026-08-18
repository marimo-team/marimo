# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec
from inline_snapshot import snapshot

from marimo._data.data_source_discovery.plugins.duckdb import discover
from marimo._data.data_source_discovery.types import DiscoveryContext


def test_discovers_motherduck_environment() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "MOTHERDUCK_TOKEN": "secret-md-token",
                "MOTHERDUCK_DATABASE": "production_analytics",
            }
        )
    )

    builtins = msgspec.json.decode(msgspec.json.encode(detected))
    assert builtins == snapshot(
        [
            {
                "id": "motherduck-environment",
                "integration": "motherduck",
                "category": "database",
                "displayName": "MotherDuck",
                "confidence": "high",
                "origins": [
                    {
                        "type": "environment",
                        "label": "Kernel environment",
                    }
                ],
                "configuration": [
                    {
                        "field": "Token",
                        "value": {
                            "kind": "environment-variable",
                            "name": "MOTHERDUCK_TOKEN",
                        },
                    },
                    {
                        "field": "Database",
                        "value": {
                            "kind": "environment-variable",
                            "name": "MOTHERDUCK_DATABASE",
                        },
                    },
                ],
                "code": "import os\nimport duckdb\n\ncon = duckdb.connect(f\"md:{os.environ['MOTHERDUCK_DATABASE']}\")",
            }
        ]
    )


def test_discovers_motherduck_without_database() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "MOTHERDUCK_TOKEN": "secret-md-token",
            }
        )
    )

    assert len(detected) == 1
    assert detected[0].id == "motherduck-environment"
    assert detected[0].display_name == "MotherDuck"
    assert 'con = duckdb.connect("md:")' in detected[0].code


def test_discovers_quack_protocol_token() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "QUACK_TOKEN": "secret-quack-token",
                "QUACK_DATABASE": "quack:my_sample_lake",
            }
        )
    )

    builtins = msgspec.json.decode(msgspec.json.encode(detected))
    assert builtins == snapshot(
        [
            {
                "id": "duckdb-quack-environment",
                "integration": "duckdb",
                "category": "database",
                "displayName": "DuckDB (Quack Protocol)",
                "confidence": "high",
                "origins": [
                    {
                        "type": "environment",
                        "label": "Kernel environment",
                    }
                ],
                "configuration": [
                    {
                        "field": "Token",
                        "value": {
                            "kind": "environment-variable",
                            "name": "QUACK_TOKEN",
                        },
                    },
                    {
                        "field": "Database",
                        "value": {
                            "kind": "environment-variable",
                            "name": "QUACK_DATABASE",
                        },
                    },
                ],
                "code": 'import os\nimport duckdb\n\ncon = duckdb.connect(os.environ["QUACK_DATABASE"])',
            }
        ]
    )


def test_discovers_quack_protocol_prefix_in_duckdb_database() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "DUCKDB_DATABASE": "quack://analytics_catalog",
            }
        )
    )

    assert len(detected) == 1
    assert detected[0].id == "duckdb-quack-environment"
    assert detected[0].display_name == "DuckDB (Quack Protocol)"
    assert detected[0].category == "database"
    assert (
        'con = duckdb.connect(os.environ["DUCKDB_DATABASE"])'
        in detected[0].code
    )


def test_discovers_quack_protocol_api_key() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "QUACK_API_KEY": "secret-quack-key",
            }
        )
    )

    assert len(detected) == 1
    assert detected[0].id == "duckdb-quack-environment"
    assert 'con = duckdb.connect("quack:")' in detected[0].code


def test_discovers_local_duckdb_file() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "DUCKDB_PATH": "/tmp/warehouse.duckdb",
            }
        )
    )

    builtins = msgspec.json.decode(msgspec.json.encode(detected))
    assert builtins == snapshot(
        [
            {
                "id": "duckdb-local-environment",
                "integration": "duckdb",
                "category": "database",
                "displayName": "DuckDB",
                "confidence": "high",
                "origins": [
                    {
                        "type": "environment",
                        "label": "Kernel environment",
                    }
                ],
                "configuration": [
                    {
                        "field": "Database Path",
                        "value": {
                            "kind": "environment-variable",
                            "name": "DUCKDB_PATH",
                        },
                    },
                ],
                "code": 'import os\nimport duckdb\n\ncon = duckdb.connect(os.environ["DUCKDB_PATH"])',
            }
        ]
    )


def test_discovers_local_duckdb_read_only() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "DUCKDB_PATH": "/data/readonly.duckdb",
                "DUCKDB_READ_ONLY": "true",
            }
        )
    )

    assert len(detected) == 1
    assert detected[0].id == "duckdb-local-environment"
    assert "read_only=True" in detected[0].code


def test_empty_environment_returns_empty() -> None:
    assert discover(DiscoveryContext(environment={})) == []


def test_discovers_multiple_datasources() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "MOTHERDUCK_TOKEN": "secret-md",
                "QUACK_TOKEN": "secret-quack",
                "DUCKDB_PATH": "/data/local.duckdb",
            }
        )
    )

    ids = [item.id for item in detected]
    assert "motherduck-environment" in ids
    assert "duckdb-quack-environment" in ids
    assert "duckdb-local-environment" in ids

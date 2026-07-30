# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec
from inline_snapshot import snapshot

from marimo._data.data_source_discovery.plugins.postgres import discover
from marimo._data.data_source_discovery.types import DiscoveryContext


def test_discovers_libpq_environment() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "PGHOST": "secret-host",
                "PGPORT": "5432",
                "PGUSER": "secret-user",
                "PGPASSWORD": "secret-password",
                "PGDATABASE": "secret-database",
            }
        )
    )

    assert msgspec.json.decode(msgspec.json.encode(detected)) == snapshot(
        [
            {
                "id": "postgres-libpq-environment",
                "integration": "postgres",
                "category": "database",
                "displayName": "PostgreSQL",
                "confidence": "high",
                "origins": [
                    {
                        "type": "environment",
                        "label": "Kernel environment",
                    }
                ],
                "configuration": [
                    {
                        "field": "Host",
                        "value": {
                            "kind": "environment-variable",
                            "name": "PGHOST",
                        },
                    },
                    {
                        "field": "Username",
                        "value": {
                            "kind": "environment-variable",
                            "name": "PGUSER",
                        },
                    },
                    {
                        "field": "Database",
                        "value": {
                            "kind": "environment-variable",
                            "name": "PGDATABASE",
                        },
                    },
                    {
                        "field": "Port",
                        "value": {
                            "kind": "environment-variable",
                            "name": "PGPORT",
                        },
                    },
                    {
                        "field": "Password",
                        "value": {
                            "kind": "environment-variable",
                            "name": "PGPASSWORD",
                        },
                    },
                ],
                "code": """\
import os
import sqlalchemy

DATABASE_URL = sqlalchemy.URL.create(
    "postgresql",
    username=os.environ["PGUSER"],
    password=os.environ["PGPASSWORD"],
    host=os.environ["PGHOST"],
    port=int(os.environ["PGPORT"]),
    database=os.environ["PGDATABASE"],
)
engine = sqlalchemy.create_engine(DATABASE_URL)""",
            }
        ]
    )


def test_ignores_partial_libpq_environment() -> None:
    detected = discover(
        DiscoveryContext(environment={"PGHOST": "host", "PGUSER": "user"})
    )

    assert detected == snapshot([])


def test_ignores_empty_required_value() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "PGHOST": "host",
                "PGUSER": "",
                "PGDATABASE": "database",
            }
        )
    )

    assert detected == snapshot([])


def test_uses_defaults_for_empty_optional_values() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "PGHOST": "host",
                "PGUSER": "user",
                "PGDATABASE": "database",
                "PGPORT": "",
                "PGPASSWORD": "",
            }
        )
    )

    assert "port=5432" in detected[0].code
    assert "PGPORT" not in detected[0].code
    assert "PGPASSWORD" not in detected[0].code

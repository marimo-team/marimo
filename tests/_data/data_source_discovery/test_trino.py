# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast

import msgspec
import pytest
from inline_snapshot import snapshot

from marimo._data.data_source_discovery.plugins.trino import discover
from marimo._data.data_source_discovery.types import DiscoveryContext


def test_discovers_complete_trino_environment() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "TRINO_HOST": "secret-host",
                "TRINO_PORT": "61234",
                "TRINO_USER": "secret-user",
                "TRINO_PASSWORD": "secret-password",
                "TRINO_CATALOG": "secret-catalog",
                "TRINO_SCHEMA": "secret-schema",
            }
        )
    )

    builtins = msgspec.json.decode(msgspec.json.encode(detected))
    assert builtins == snapshot(
        [
            {
                "id": "trino-environment",
                "integration": "trino",
                "category": "database",
                "displayName": "Trino",
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
                            "name": "TRINO_HOST",
                        },
                    },
                    {
                        "field": "Port",
                        "value": {
                            "kind": "environment-variable",
                            "name": "TRINO_PORT",
                        },
                    },
                    {
                        "field": "Username",
                        "value": {
                            "kind": "environment-variable",
                            "name": "TRINO_USER",
                        },
                    },
                    {
                        "field": "Password",
                        "value": {
                            "kind": "environment-variable",
                            "name": "TRINO_PASSWORD",
                        },
                    },
                    {
                        "field": "Catalog",
                        "value": {
                            "kind": "environment-variable",
                            "name": "TRINO_CATALOG",
                        },
                    },
                    {
                        "field": "Schema",
                        "value": {
                            "kind": "environment-variable",
                            "name": "TRINO_SCHEMA",
                        },
                    },
                ],
                "code": """\
import os
import sqlalchemy
import trino.sqlalchemy
from trino.auth import BasicAuthentication

connect_args = {
    "auth": BasicAuthentication(
        os.environ["TRINO_USER"],
        os.environ["TRINO_PASSWORD"],
    ),
    "http_scheme": "https",
}

database = os.environ["TRINO_CATALOG"]
database += "/" + os.environ["TRINO_SCHEMA"]
TRINO_URL = sqlalchemy.URL.create(
    "trino",
    username=os.environ["TRINO_USER"],
    host=os.environ["TRINO_HOST"],
    port=int(os.environ["TRINO_PORT"]),
    database=database,
)
engine = sqlalchemy.create_engine(TRINO_URL, connect_args=connect_args)""",
            }
        ]
    )
    ast.parse(detected[0].code)
    assert "secret-" not in repr(builtins)


def test_uses_trino_defaults_for_optional_variables() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "TRINO_HOST": "secret-host",
                "TRINO_USER": "secret-user",
                "TRINO_CATALOG": "secret-catalog",
                "TRINO_PORT": "",
                "TRINO_PASSWORD": "",
                "TRINO_SCHEMA": "",
            }
        )
    )

    assert msgspec.json.decode(msgspec.json.encode(detected)) == snapshot(
        [
            {
                "id": "trino-environment",
                "integration": "trino",
                "category": "database",
                "displayName": "Trino",
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
                            "name": "TRINO_HOST",
                        },
                    },
                    {
                        "field": "Username",
                        "value": {
                            "kind": "environment-variable",
                            "name": "TRINO_USER",
                        },
                    },
                    {
                        "field": "Catalog",
                        "value": {
                            "kind": "environment-variable",
                            "name": "TRINO_CATALOG",
                        },
                    },
                ],
                "code": """\
import os
import sqlalchemy
import trino.sqlalchemy

database = os.environ["TRINO_CATALOG"]
TRINO_URL = sqlalchemy.URL.create(
    "trino",
    username=os.environ["TRINO_USER"],
    host=os.environ["TRINO_HOST"],
    port=8080,
    database=database,
)
engine = sqlalchemy.create_engine(TRINO_URL)""",
            }
        ]
    )


def test_password_without_port_does_not_change_default_port() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "TRINO_HOST": "secret-host",
                "TRINO_USER": "secret-user",
                "TRINO_PASSWORD": "secret-password",
                "TRINO_CATALOG": "secret-catalog",
            }
        )
    )

    assert [
        line.strip()
        for line in detected[0].code.splitlines()
        if "http_scheme" in line or "port=" in line
    ] == snapshot(
        [
            '"http_scheme": "https",',
            "port=8080,",
        ]
    )


@pytest.mark.parametrize(
    "port",
    [
        "not-a-port",
        "0",
        "-1",
        "65536",
    ],
)
def test_invalid_port_uses_default(port: str) -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "TRINO_HOST": "secret-host",
                "TRINO_PORT": port,
                "TRINO_USER": "secret-user",
                "TRINO_CATALOG": "secret-catalog",
            }
        )
    )

    assert [
        configuration.field for configuration in detected[0].configuration
    ] == snapshot(["Host", "Username", "Catalog"])
    assert "port=8080" in detected[0].code
    assert "TRINO_PORT" not in detected[0].code


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"TRINO_HOST": "host", "TRINO_USER": "user"},
        {
            "TRINO_HOST": "",
            "TRINO_USER": "user",
            "TRINO_CATALOG": "catalog",
        },
        {
            "TRINO_HOST": "host",
            "TRINO_USER": "",
            "TRINO_CATALOG": "catalog",
        },
        {
            "TRINO_HOST": "host",
            "TRINO_USER": "user",
            "TRINO_CATALOG": "",
        },
    ],
)
def test_ignores_incomplete_trino_environment(
    environment: dict[str, str],
) -> None:
    assert discover(DiscoveryContext(environment=environment)) == snapshot([])

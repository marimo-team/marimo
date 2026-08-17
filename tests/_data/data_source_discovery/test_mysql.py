# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec
from inline_snapshot import snapshot

from marimo._data.data_source_discovery.plugins.mysql import discover
from marimo._data.data_source_discovery.types import DiscoveryContext


def test_discovers_mysql_environment() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "MYSQL_HOST": "secret-host",
                "MYSQL_TCP_PORT": "3306",
                "MYSQL_USER": "secret-user",
                "MYSQL_PWD": "secret-password",
                "MYSQL_DATABASE": "secret-database",
            }
        )
    )

    builtins = msgspec.json.decode(msgspec.json.encode(detected))
    assert builtins == snapshot(
        [
            {
                "id": "mysql-environment",
                "integration": "mysql",
                "category": "database",
                "displayName": "MySQL",
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
                            "name": "MYSQL_HOST",
                        },
                    },
                    {
                        "field": "Username",
                        "value": {
                            "kind": "environment-variable",
                            "name": "MYSQL_USER",
                        },
                    },
                    {
                        "field": "Password",
                        "value": {
                            "kind": "environment-variable",
                            "name": "MYSQL_PWD",
                        },
                    },
                    {
                        "field": "Database",
                        "value": {
                            "kind": "environment-variable",
                            "name": "MYSQL_DATABASE",
                        },
                    },
                    {
                        "field": "Port",
                        "value": {
                            "kind": "environment-variable",
                            "name": "MYSQL_TCP_PORT",
                        },
                    },
                ],
                "code": """\
import os
import sqlalchemy

DATABASE_URL = sqlalchemy.URL.create(
    "mysql+pymysql",
    username=os.environ["MYSQL_USER"],
    password=os.environ["MYSQL_PWD"],
    host=os.environ["MYSQL_HOST"],
    port=int(os.environ["MYSQL_TCP_PORT"]),
    database=os.environ["MYSQL_DATABASE"],
)
engine = sqlalchemy.create_engine(DATABASE_URL)""",
                "configured": False,
            }
        ]
    )
    assert "secret-" not in repr(builtins)


def test_ignores_partial_mysql_environment() -> None:
    detected = discover(
        DiscoveryContext(
            environment={"MYSQL_HOST": "host", "MYSQL_USER": "user"}
        )
    )

    assert detected == snapshot([])


def test_discovers_mysql_password_environment() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "MYSQL_HOST": "secret-host",
                "MYSQL_USER": "secret-user",
                "MYSQL_PASSWORD": "secret-password",
                "MYSQL_DATABASE": "secret-database",
            }
        )
    )

    builtins = msgspec.json.decode(msgspec.json.encode(detected))
    assert builtins[0]["configuration"][2] == snapshot(
        {
            "field": "Password",
            "value": {
                "kind": "environment-variable",
                "name": "MYSQL_PASSWORD",
            },
        }
    )
    assert 'password=os.environ["MYSQL_PASSWORD"]' in builtins[0]["code"]
    assert "secret-" not in repr(builtins)


def test_prefers_mysql_password_over_mysql_pwd() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "MYSQL_HOST": "host",
                "MYSQL_USER": "user",
                "MYSQL_PASSWORD": "password",
                "MYSQL_PWD": "legacy-password",
                "MYSQL_DATABASE": "database",
            }
        )
    )

    builtins = msgspec.json.decode(msgspec.json.encode(detected))
    assert builtins[0]["configuration"][2] == snapshot(
        {
            "field": "Password",
            "value": {
                "kind": "environment-variable",
                "name": "MYSQL_PASSWORD",
            },
        }
    )
    assert 'password=os.environ["MYSQL_PASSWORD"]' in detected[0].code
    assert "MYSQL_PWD" not in detected[0].code


def test_ignores_empty_required_value() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "MYSQL_HOST": "host",
                "MYSQL_USER": "user",
                "MYSQL_PWD": "",
                "MYSQL_DATABASE": "database",
            }
        )
    )

    assert detected == snapshot([])


def test_ignores_environment_without_password() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "MYSQL_HOST": "host",
                "MYSQL_USER": "user",
                "MYSQL_DATABASE": "database",
            }
        )
    )

    assert detected == snapshot([])


def test_uses_default_for_empty_optional_port() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "MYSQL_HOST": "host",
                "MYSQL_USER": "user",
                "MYSQL_PWD": "password",
                "MYSQL_DATABASE": "database",
                "MYSQL_TCP_PORT": "",
            }
        )
    )

    assert "port=3306" in detected[0].code
    assert "MYSQL_TCP_PORT" not in detected[0].code


def test_uses_default_for_malformed_optional_port() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "MYSQL_HOST": "host",
                "MYSQL_USER": "user",
                "MYSQL_PWD": "password",
                "MYSQL_DATABASE": "database",
                "MYSQL_TCP_PORT": "not-a-port",
            }
        )
    )

    builtins = msgspec.json.decode(msgspec.json.encode(detected))
    assert [
        item["field"] for item in builtins[0]["configuration"]
    ] == snapshot(["Host", "Username", "Password", "Database"])
    assert "port=3306" in detected[0].code
    assert "MYSQL_TCP_PORT" not in detected[0].code

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import sys
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING

import msgspec
from inline_snapshot import snapshot

from marimo._data.data_source_discovery.plugins.databricks import discover
from marimo._data.data_source_discovery.types import DiscoveryContext

if TYPE_CHECKING:
    import pytest


def test_discovers_databricks_sql_warehouse() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "DATABRICKS_SQL_WAREHOUSE_ID": "secret-warehouse-id",
            }
        )
    )

    builtins = msgspec.json.decode(msgspec.json.encode(detected))
    assert builtins == snapshot(
        [
            {
                "id": "databricks-sql-warehouse-environment",
                "integration": "databricks",
                "category": "database",
                "displayName": "Databricks SQL warehouse",
                "confidence": "high",
                "origins": [
                    {
                        "type": "environment",
                        "label": "Kernel environment",
                    }
                ],
                "configuration": [
                    {
                        "field": "SQL warehouse",
                        "value": {
                            "kind": "environment-variable",
                            "name": "DATABRICKS_SQL_WAREHOUSE_ID",
                        },
                    }
                ],
                "code": """\
import os
from urllib.parse import urlsplit

from databricks import sql
from databricks.sdk import WorkspaceClient

workspace = WorkspaceClient()
connection = sql.connect(
    server_hostname=urlsplit(workspace.config.host).hostname,
    http_path=(
        "/sql/1.0/warehouses/"
        + os.environ["DATABRICKS_SQL_WAREHOUSE_ID"]
    ),
    access_token=workspace.config.authenticate()[
        "Authorization"
    ].removeprefix("Bearer "),
)""",
                "hidesWhen": {
                    "kind": "dialect",
                    "substrings": ["databricks"],
                },
            }
        ]
    )
    ast.parse(detected[0].code)
    assert "secret-warehouse-id" not in repr(builtins)


def test_uses_optional_databricks_profile() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "DATABRICKS_SQL_WAREHOUSE_ID": "secret-warehouse-id",
                "DATABRICKS_CONFIG_PROFILE": "secret-profile",
            }
        )
    )

    builtins = msgspec.json.decode(msgspec.json.encode(detected))
    assert builtins[0]["configuration"] == snapshot(
        [
            {
                "field": "SQL warehouse",
                "value": {
                    "kind": "environment-variable",
                    "name": "DATABRICKS_SQL_WAREHOUSE_ID",
                },
            },
            {
                "field": "Profile",
                "value": {
                    "kind": "environment-variable",
                    "name": "DATABRICKS_CONFIG_PROFILE",
                },
            },
        ]
    )
    assert (
        """\
workspace = WorkspaceClient(
    profile=os.environ["DATABRICKS_CONFIG_PROFILE"]
)"""
        in detected[0].code
    )
    ast.parse(detected[0].code)
    assert "secret-" not in repr(builtins)


def test_ignores_missing_or_empty_warehouse_id() -> None:
    assert discover(DiscoveryContext(environment={})) == snapshot([])
    assert discover(
        DiscoveryContext(environment={"DATABRICKS_SQL_WAREHOUSE_ID": ""})
    ) == snapshot([])


def test_generated_code_connects_with_unified_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profiles: list[str | None] = []
    connection_arguments: list[dict[str, object]] = []
    expected_connection = object()

    class WorkspaceClient:
        def __init__(self, *, profile: str | None = None) -> None:
            profiles.append(profile)
            self.config = SimpleNamespace(
                host="https://workspace.cloud.databricks.com",
                authenticate=lambda: {
                    "Authorization": "Bearer secret-access-token"
                },
            )

    def connect(**kwargs: object) -> object:
        connection_arguments.append(kwargs)
        return expected_connection

    databricks = ModuleType("databricks")
    databricks_sql = ModuleType("databricks.sql")
    databricks_sql.connect = connect  # type: ignore[attr-defined]
    databricks.sql = databricks_sql  # type: ignore[attr-defined]
    databricks_sdk = ModuleType("databricks.sdk")
    databricks_sdk.WorkspaceClient = WorkspaceClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "databricks", databricks)
    monkeypatch.setitem(sys.modules, "databricks.sql", databricks_sql)
    monkeypatch.setitem(sys.modules, "databricks.sdk", databricks_sdk)
    monkeypatch.setenv("DATABRICKS_SQL_WAREHOUSE_ID", "warehouse-id")
    monkeypatch.setenv("DATABRICKS_CONFIG_PROFILE", "analytics")

    source = discover(
        DiscoveryContext(
            environment={
                "DATABRICKS_SQL_WAREHOUSE_ID": "warehouse-id",
                "DATABRICKS_CONFIG_PROFILE": "analytics",
            }
        )
    )[0]
    namespace: dict[str, object] = {}
    exec(compile(source.code, "<databricks-discovery>", "exec"), namespace)

    assert profiles == snapshot(["analytics"])
    assert connection_arguments == snapshot(
        [
            {
                "server_hostname": "workspace.cloud.databricks.com",
                "http_path": "/sql/1.0/warehouses/warehouse-id",
                "access_token": "secret-access-token",
            }
        ]
    )
    assert namespace["connection"] is expected_connection

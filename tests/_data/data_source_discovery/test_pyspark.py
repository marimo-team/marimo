# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import sys
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING

import msgspec
from inline_snapshot import snapshot

from marimo._data.data_source_discovery.plugins.pyspark import discover
from marimo._data.data_source_discovery.types import DiscoveryContext

if TYPE_CHECKING:
    import pytest


def test_discovers_spark_connect_environment() -> None:
    detected = discover(
        DiscoveryContext(
            environment={"SPARK_REMOTE": "sc://secret-host:61235"}
        )
    )

    builtins = msgspec.json.decode(msgspec.json.encode(detected))
    assert builtins == snapshot(
        [
            {
                "id": "pyspark-connect-environment",
                "integration": "pyspark",
                "category": "database",
                "displayName": "PySpark (Spark Connect)",
                "confidence": "high",
                "origins": [
                    {
                        "type": "environment",
                        "label": "Kernel environment",
                    }
                ],
                "configuration": [
                    {
                        "field": "Remote",
                        "value": {
                            "kind": "environment-variable",
                            "name": "SPARK_REMOTE",
                        },
                    }
                ],
                "code": """\
import os
import ibis
from pyspark.sql import SparkSession

session = SparkSession.builder.remote(
    os.environ["SPARK_REMOTE"]
).getOrCreate()
con = ibis.pyspark.connect(session)""",
            }
        ]
    )
    ast.parse(detected[0].code)
    assert "secret-host" not in repr(builtins)


def test_ignores_missing_or_empty_spark_remote() -> None:
    assert discover(DiscoveryContext(environment={})) == snapshot([])
    assert discover(
        DiscoveryContext(environment={"SPARK_REMOTE": ""})
    ) == snapshot([])
    assert discover(
        DiscoveryContext(environment={"SPARK_HOME": "/secret/spark"})
    ) == snapshot([])


def test_generated_code_creates_remote_ibis_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remote_urls: list[str] = []
    session = object()
    connections: list[object] = []

    class Builder:
        def remote(self, url: str) -> Builder:
            remote_urls.append(url)
            return self

        def getOrCreate(self) -> object:
            return session

    class SparkSession:
        builder = Builder()

    pyspark = ModuleType("pyspark")
    pyspark_sql = ModuleType("pyspark.sql")
    pyspark_sql.SparkSession = SparkSession  # type: ignore[attr-defined]
    ibis = ModuleType("ibis")
    ibis.pyspark = SimpleNamespace(  # type: ignore[attr-defined]
        connect=lambda value: connections.append(value) or "connection"
    )
    monkeypatch.setitem(sys.modules, "pyspark", pyspark)
    monkeypatch.setitem(sys.modules, "pyspark.sql", pyspark_sql)
    monkeypatch.setitem(sys.modules, "ibis", ibis)
    monkeypatch.setenv("SPARK_REMOTE", "sc://spark.example:15002")

    source = discover(
        DiscoveryContext(
            environment={"SPARK_REMOTE": "sc://spark.example:15002"}
        )
    )[0]
    namespace: dict[str, object] = {}
    exec(compile(source.code, "<pyspark-discovery>", "exec"), namespace)

    assert remote_urls == snapshot(["sc://spark.example:15002"])
    assert connections == [session]
    assert namespace["con"] == "connection"

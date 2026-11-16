# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import msgspec
import pytest

from marimo._data.data_source_discovery import discover_data_sources
from marimo._data.data_source_discovery.plugins.duckdb import DUCKDB_PLUGIN
from marimo._messaging.notification import (
    DataSourceDiscoveryResultNotification,
)
from marimo._runtime.commands import (
    DiscoverDataSourcesCommand,
    ExecuteCellCommand,
)
from marimo._types.ids import CellId_t, RequestId
from tests.conftest import MockedKernel


@pytest.mark.parametrize(
    ("environment", "integrations"),
    [
        (
            {
                "PGHOST": "secret-pg-host",
                "PGUSER": "secret-pg-user",
                "PGDATABASE": "secret-pg-database",
            },
            ["postgres"],
        ),
        (
            {
                "DUCKDB_DATABASE": "md:secret-production",
                "MOTHERDUCK_TOKEN": "secret-token",
            },
            ["motherduck"],
        ),
        (
            {
                "DUCKDB_DATABASE": "quack://secret-host",
                "QUACK_API_KEY": "secret-token",
            },
            ["duckdb"],
        ),
        ({"DUCKDB_PATH": "/secret/local.duckdb"}, ["duckdb"]),
        (
            {
                "MOTHERDUCK_TOKEN": "secret-motherduck",
                "DUCKDB_PATH": "/secret/local.duckdb",
                "QUACK_DATABASE": "quack:secret-host",
                "QUACK_TOKEN": "secret-quack",
            },
            ["motherduck", "duckdb", "duckdb"],
        ),
    ],
)
async def test_discovery_reads_live_kernel_environment(
    mocked_kernel: MockedKernel,
    environment: dict[str, str],
    integrations: list[str],
) -> None:
    kernel = mocked_kernel.k
    stream = mocked_kernel.stream

    with (
        patch.dict(
            os.environ,
            environment,
            clear=True,
        ),
        patch(
            "marimo._data.data_source_discovery.plugins.pyiceberg."
            "_load_resolved_catalogs",
            return_value={},
        ) as load_resolved_catalogs,
    ):
        await kernel.handle_message(
            DiscoverDataSourcesCommand(request_id=RequestId("discovery"))
        )

    results = [
        operation
        for operation in stream.operations
        if isinstance(operation, DataSourceDiscoveryResultNotification)
    ]
    assert len(results) == 1
    assert results[0].request_id == RequestId("discovery")
    assert [
        source.integration for source in results[0].sources
    ] == integrations
    payload = msgspec.json.encode(results[0]).decode()
    for value in environment.values():
        assert value not in payload
    load_resolved_catalogs.assert_called_once_with(environment=environment)


@pytest.mark.requires("duckdb")
@pytest.mark.parametrize(
    ("source_id", "connection_name"),
    [
        ("motherduck-environment", "motherduck_con"),
        ("duckdb-quack-environment", "quack_con"),
        ("duckdb-local-environment", "duckdb_con"),
    ],
)
async def test_duckdb_suggestion_runs_in_kernel(
    mocked_kernel: MockedKernel,
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    connection_name: str,
) -> None:
    import duckdb

    environment = {
        "MOTHERDUCK_DATABASE": "analytics",
        "MOTHERDUCK_TOKEN": "motherduck-token",
        "QUACK_DATABASE": "quack:localhost",
        "QUACK_TOKEN": "quack-token",
        "DUCKDB_PATH": ":memory:",
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    source = next(
        source
        for source in discover_data_sources(
            environment, plugins=(DUCKDB_PLUGIN,)
        )
        if source.id == source_id
    )
    kernel = mocked_kernel.k
    await kernel.run(
        [
            ExecuteCellCommand(
                cell_id=CellId_t("existing"), code="con = object()"
            )
        ]
    )
    existing_con = kernel.globals["con"]
    connection = MagicMock(spec=["execute", "close"])
    with (
        patch.object(duckdb, "__version__", "2.0.0"),
        patch.object(duckdb, "connect", return_value=connection) as connect,
    ):
        await kernel.run(
            [
                ExecuteCellCommand(
                    cell_id=CellId_t("connection"), code=source.code
                )
            ]
        )
    assert kernel.errors == {}
    connect.assert_called_once()
    assert kernel.globals[connection_name] is connection
    assert kernel.globals["con"] is existing_con
    assert kernel.globals["duckdb"] is duckdb
    assert kernel.globals["os"] is os

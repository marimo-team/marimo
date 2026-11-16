# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from unittest.mock import patch

import msgspec
import pytest

from marimo._messaging.notification import (
    DataSourceDiscoveryResultNotification,
)
from marimo._runtime.commands import DiscoverDataSourcesCommand
from marimo._types.ids import RequestId
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

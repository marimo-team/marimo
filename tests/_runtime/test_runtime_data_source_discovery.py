# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from unittest.mock import patch

from marimo._messaging.notification import (
    DataSourceDiscoveryResultNotification,
)
from marimo._runtime.commands import DiscoverDataSourcesCommand
from marimo._types.ids import RequestId
from tests.conftest import MockedKernel


async def test_discovery_reads_live_kernel_environment(
    mocked_kernel: MockedKernel,
) -> None:
    kernel = mocked_kernel.k
    stream = mocked_kernel.stream

    with (
        patch.dict(
            os.environ,
            {
                "PGHOST": "host",
                "PGUSER": "user",
                "PGDATABASE": "database",
            },
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
    assert [source.integration for source in results[0].sources] == [
        "postgres"
    ]
    load_resolved_catalogs.assert_called_once_with()

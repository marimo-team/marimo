# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock, patch

from marimo._save.stores import rest


def test_get_logs_unexpected_response_status() -> None:
    store = rest.RestStore(
        base_url="https://cache.example.com", api_key="test-key"
    )
    response = MagicMock()
    response.status = 500
    response.__enter__.return_value = response

    with (
        patch.object(rest.urllib.request, "urlopen", return_value=response),
        patch.object(rest.LOGGER, "warning") as warning,
    ):
        result = store.get("cache-key")

    assert result is None
    warning.assert_called_once_with(
        "GET %s - Unexpected status: %s",
        "https://cache.example.com/cache-key",
        500,
    )

# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import urllib.error
from datetime import datetime
from typing import Any
from unittest.mock import mock_open, patch

from marimo._cli.upgrade import (
    _update_with_latest_version,
    check_for_updates,
    print_latest_version,
)
from marimo._config.cli_state import MarimoCLIState


@patch("marimo._cli.upgrade.current_version", "0.1.0")
@patch("marimo._utils.config.config.os.path.exists")
@patch("marimo._utils.config.config.os.makedirs")
@patch(
    "__main__.open",
    new_callable=mock_open,
)
@patch("marimo._cli.upgrade._update_with_latest_version")
@patch("marimo._cli.upgrade.echo")
def test_check_for_updates(
    mock_echo: Any,
    mock_update_with_latest_version: Any,
    mock_open_file: Any,
    mock_makedirs: Any,
    mock_path_exists: Any,
) -> None:
    # Mocks
    mock_update_with_latest_version.return_value = MarimoCLIState(
        latest_version="0.1.2", last_checked_at="2020-01-01"
    )
    mock_path_exists.return_value = True
    mock_open_file.side_effect = FileNotFoundError()

    # Call the function to test
    check_for_updates(print_latest_version)

    # Assert that the makedirs function was not called
    mock_makedirs.assert_not_called()

    mock_echo.assert_called()

    # Assert prints
    assert any(
        "0.1.0 → 0.1.2" in call[0][0] for call in mock_echo.call_args_list
    )
    assert any(
        "pip install --upgrade marimo" in call[0][0]
        for call in mock_echo.call_args_list
    )


@patch("marimo._cli.upgrade._fetch_data_from_url")
def test_update_with_latest_version(mock_fetch_data_from_url: Any) -> None:
    # Mocks
    state = MarimoCLIState(
        latest_version="0.1.0", last_checked_at="2020-01-01"
    )
    mock_fetch_data_from_url.return_value = {"info": {"version": "0.1.2"}}

    updated_state = _update_with_latest_version(state)

    # Assert that the latest_version was updated
    assert updated_state.latest_version == "0.1.2"
    # Assert that the last_checked_at was updated to the current date
    today = datetime.now().date()
    assert updated_state.last_checked_at == today.strftime("%Y-%m-%d")


@patch("marimo._cli.upgrade._fetch_data_from_url")
def test_update_with_latest_version_fails(
    mock_fetch_data_from_url: Any,
) -> None:
    # Mocks
    state = MarimoCLIState(
        latest_version="0.1.0", last_checked_at="2020-01-01"
    )
    # Raises
    mock_fetch_data_from_url.side_effect = Exception("pypi down!")

    # Run
    updated_state = _update_with_latest_version(state)

    # Assert state is unchanged
    assert state == updated_state


@patch("marimo._cli.upgrade._fetch_data_from_url")
def test_update_with_within_the_same_day(
    mock_fetch_data_from_url: Any,
) -> None:
    # Mocks
    state = MarimoCLIState(
        latest_version="0.1.0",
        last_checked_at=datetime.now().date().strftime("%Y-%m-%d"),
    )

    # Run
    updated_state = _update_with_latest_version(state)

    # Assert state is unchanged
    assert state == updated_state
    # Assert that the _fetch_data_from_url was not called
    mock_fetch_data_from_url.assert_not_called()


@patch("marimo._cli.upgrade.current_version", "0.1.0")
@patch("marimo._cli.upgrade._fetch_data_from_url")
def test_version_comparison_edge_cases(mock_fetch_data_from_url: Any) -> None:
    # Test same version
    mock_fetch_data_from_url.return_value = {"info": {"version": "0.1.0"}}
    with patch("marimo._cli.upgrade.echo") as mock_echo:
        check_for_updates(print_latest_version)
        mock_echo.assert_not_called()

    # Test pre-release version
    mock_fetch_data_from_url.return_value = {
        "info": {"version": "0.2.0-alpha.1"}
    }
    with patch("marimo._cli.upgrade.echo") as mock_echo:
        check_for_updates(print_latest_version)
        mock_echo.assert_called()

    # Test lower version (shouldn't happen in practice)
    mock_fetch_data_from_url.return_value = {"info": {"version": "0.0.9"}}
    with patch("marimo._cli.upgrade.echo") as mock_echo:
        check_for_updates(print_latest_version)
        mock_echo.assert_not_called()


@patch("marimo._cli.upgrade._fetch_data_from_url")
def test_network_errors(mock_fetch_data_from_url: Any) -> None:
    state = MarimoCLIState(
        latest_version="0.1.0", last_checked_at="2020-01-01"
    )

    # Test timeout
    mock_fetch_data_from_url.side_effect = TimeoutError()
    updated_state = _update_with_latest_version(state)
    assert updated_state.latest_version == "0.1.0"  # Should keep old version

    # Test network error
    mock_fetch_data_from_url.side_effect = urllib.error.URLError(
        "Network down"
    )
    updated_state = _update_with_latest_version(state)
    assert updated_state.latest_version == "0.1.0"  # Should keep old version

    # Test invalid JSON
    mock_fetch_data_from_url.side_effect = json.JSONDecodeError(
        "Invalid JSON", "", 0
    )
    updated_state = _update_with_latest_version(state)
    assert updated_state.latest_version == "0.1.0"  # Should keep old version

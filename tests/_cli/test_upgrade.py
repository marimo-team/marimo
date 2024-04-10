# Copyright 2024 Marimo. All rights reserved.
from datetime import datetime
from typing import Any
from unittest.mock import mock_open, patch

from marimo._cli.upgrade import (
    MarimoCLIState,
    _update_with_latest_version,
    check_for_updates,
)


@patch("marimo._cli.upgrade.current_version", "0.1.0")
@patch("marimo._utils.config.config.os.path.exists")
@patch("marimo._utils.config.config.os.makedirs")
@patch(
    "__main__.open",
    new_callable=mock_open,
)
@patch("marimo._cli.upgrade._update_with_latest_version")
@patch("builtins.print")
def test_check_for_updates(
    mock_print: Any,
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
    check_for_updates()

    # Assert that the makedirs function was not called
    mock_makedirs.assert_not_called()

    # Assert prints
    assert any(
        "0.1.0 → 0.1.2" in call[0][0] for call in mock_print.call_args_list
    )
    assert any(
        "pip install --upgrade marimo" in call[0][0]
        for call in mock_print.call_args_list
    )


@patch("marimo._cli.upgrade._fetch_data_from_url")
def test_update_with_latest_version(mock_fetch_data_from_url: Any) -> None:
    # Mocks
    state = MarimoCLIState(
        latest_version="0.1.0", last_checked_at="2020-01-01"
    )
    mock_fetch_data_from_url.return_value = {"info": {"version": "0.1.2"}}

    # Run
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

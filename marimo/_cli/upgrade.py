# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Callable

import marimo._utils.requests as requests
from marimo import __version__ as current_version, _loggers
from marimo._cli.print import echo, green, orange
from marimo._config.cli_state import (
    MarimoCLIState,
    get_cli_state,
    write_cli_state,
)
from marimo._server.api.status import HTTPException
from marimo._tracer import server_tracer

FETCH_TIMEOUT = 3

LOGGER = _loggers.marimo_logger()


def print_latest_version(current_version: str, latest_version: str) -> None:
    message = f"Update available {current_version} → {latest_version}"
    echo(orange(message))
    echo(f"Run {green('pip install --upgrade marimo')} to upgrade.")
    echo()


@server_tracer.start_as_current_span("check_for_updates")
def check_for_updates(on_update: Callable[[str, str], None]) -> None:
    try:
        _check_for_updates_internal(on_update)
    except Exception as e:
        LOGGER.warning("Failed to check for updates", exc_info=e)
        # Don't want to crash the CLI on any errors.
        pass


def _check_for_updates_internal(on_update: Callable[[str, str], None]) -> None:
    from packaging import version

    state = get_cli_state()
    if not state:
        return

    # Maybe update the state with the latest version
    state = _update_with_latest_version(state)

    if not state.latest_version:
        # We couldn't get the latest version, so do nothing
        return

    # Compare versions and warn if there's a new version
    if current_version and version.parse(state.latest_version) > version.parse(
        current_version
    ):
        on_update(current_version, state.latest_version)

    # Save the state, create directories if necessary
    write_cli_state(state)


DATE_FORMAT = "%Y-%m-%d"


def _update_with_latest_version(state: MarimoCLIState) -> MarimoCLIState:
    """
    If we have not saved the latest version,
    or it's newer than the one we have, update it.
    """
    # querying pypi is +250kb and there is not a better API
    # this endpoint just returns the version
    # so we only use pypi in tests
    is_test = os.environ.get("MARIMO_PYTEST_HOME_DIR") is not None
    if is_test:
        api_url = "https://pypi.org/pypi/marimo/json"
    else:
        api_url = "https://marimo.io/api/oss/latest-version"

    # We only update the state once a day
    now = datetime.now()
    if state.last_checked_at:
        last_checked_date = datetime.strptime(
            state.last_checked_at, DATE_FORMAT
        )
        if _is_same_day(last_checked_date, now):
            # Same day, so do nothing
            return state

    try:
        # Fetch the latest version from PyPI
        response = _fetch_data_from_url(api_url)
        version = response["info"]["version"]
        state.latest_version = version
        state.last_checked_at = now.strftime(DATE_FORMAT)
        return state
    except Exception:
        # Set that we have checked for updates
        # so we don't fail multiple times a day
        state.last_checked_at = now.strftime(DATE_FORMAT)
        return state


def _fetch_data_from_url(url: str) -> dict[str, Any]:
    try:
        response = requests.get(url, timeout=FETCH_TIMEOUT)
        status = response.status_code
        if status == 200:
            return response.json()
        else:
            raise HTTPException(
                status_code=status,
                detail=f"HTTP request failed with status code {status}",
            )
    except urllib.error.URLError as e:
        LOGGER.warning(
            f"Network error while checking for version updates: {e}"
        )
        raise
    except json.JSONDecodeError as e:
        LOGGER.warning(f"Invalid JSON response from version check: {e}")
        raise
    except TimeoutError:
        LOGGER.warning(
            f"Timeout ({FETCH_TIMEOUT}s) while checking for version updates"
        )
        raise


def _is_same_day(date1: datetime, date2: datetime) -> bool:
    return date1.date() == date2.date()

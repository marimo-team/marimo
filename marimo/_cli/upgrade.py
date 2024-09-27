# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from packaging import version

from marimo import __version__ as current_version
from marimo._cli.print import echo, green, orange
from marimo._server.api.status import HTTPException
from marimo._tracer import server_tracer
from marimo._utils.config.config import ConfigReader

FETCH_TIMEOUT = 5


@dataclass
class MarimoCLIState:
    latest_version: Optional[str] = None
    last_checked_at: Optional[str] = None


def print_latest_version(current_version: str, latest_version: str) -> None:
    message = f"Update available {current_version} → {latest_version}"
    echo(orange(message))
    echo(f"Run {green('pip install --upgrade marimo')} to upgrade.")
    echo()


@server_tracer.start_as_current_span("check_for_updates")
def check_for_updates(on_update: Callable[[str, str], None]) -> None:
    try:
        _check_for_updates_internal(on_update)
    except Exception:
        # Errors are caught internally
        # but as a last resort, we don't want to crash the CLI
        pass


def _check_for_updates_internal(on_update: Callable[[str, str], None]) -> None:
    config_reader = ConfigReader.for_filename("state.toml")
    if not config_reader:
        # Couldn't find home directory, so do nothing
        return

    # Load the state file or create a default state if it doesn't exist
    state: MarimoCLIState = config_reader.read_toml(
        MarimoCLIState, fallback=MarimoCLIState()
    )

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
    config_reader.write_toml(state)


def _update_with_latest_version(state: MarimoCLIState) -> MarimoCLIState:
    """
    If we have not saved the latest version,
    or its newer than the one we have, update it.
    """
    # querying pypi is +250kb and there is not a better API
    # this endpoint just returns the version
    # so we only use pypi in tests
    is_test = os.environ.get("MARIMO_PYTEST_HOME_DIR") is not None
    if is_test:
        api_url = "https://pypi.org/pypi/marimo/json"
    else:
        api_url = "https://marimo.io/api/oss/latest-version"

    # Check if it is a different day
    if state.last_checked_at:
        last_checked_date = datetime.strptime(
            state.last_checked_at, "%Y-%m-%d"
        ).date()
        day_of_the_year = last_checked_date.timetuple().tm_yday
        today_day_of_the_year = datetime.now().timetuple().tm_yday
        if today_day_of_the_year == day_of_the_year:
            # Same day of the year, so do nothing
            return state

    # Fetch the latest version from PyPI
    try:
        response = _fetch_data_from_url(api_url)
        version = response["info"]["version"]
        state.latest_version = version
        state.last_checked_at = datetime.now().strftime("%Y-%m-%d")
        return state
    except Exception:
        # Avoid errors blocking the CLI or adding noise
        return state


def _fetch_data_from_url(url: str) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT) as response:
        status = response.status
        if status == 200:
            data = response.read()
            encoding = response.info().get_content_charset("utf-8")
            return json.loads(data.decode(encoding))  # type: ignore
        else:
            raise HTTPException(
                status_code=status,
                detail=f"HTTP request failed with status code {status}",
            )

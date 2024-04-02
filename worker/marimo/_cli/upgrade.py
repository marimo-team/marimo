# Copyright 2024 Marimo. All rights reserved.
import json
import os
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import tomlkit
from packaging import version

from marimo import __version__ as current_version
from marimo._cli.print import green, orange
from marimo._utils.parse_dataclass import parse_raw


@dataclass
class MarimoCLIState:
    latest_version: Optional[str] = None
    last_checked_at: Optional[str] = None


def check_for_updates() -> None:
    try:
        _check_for_updates_internal()
    except Exception:
        # Errors are caught internally
        # but as a last resort, we don't want to crash the CLI
        pass


def _check_for_updates_internal() -> None:
    # Find the state file
    state_file = ".marimo/state.toml"
    home_expansion = os.path.expanduser("~")
    if home_expansion == "~":
        # path expansion failed
        return None
    home_directory = os.path.realpath(home_expansion)
    file_path = os.path.join(home_directory, state_file)

    # Load the state file or create a default state if it doesn't exist
    state: MarimoCLIState
    try:
        with open(file_path, "r") as file:
            data = tomlkit.parse(file.read())
            state = parse_raw(data, MarimoCLIState)
    except FileNotFoundError:
        state = MarimoCLIState()

    # Maybe update the state with the latest version
    state = _update_with_latest_version(state)

    if not state.latest_version:
        # We couldn't get the latest version, so do nothing
        return

    # Compare versions and warn if there's a new version
    if current_version and version.parse(state.latest_version) > version.parse(
        current_version
    ):
        message = (
            f"Update available {(current_version)} → {state.latest_version}"
        )
        print(orange(message))
        print(f"Run {green('pip install --upgrade marimo')} to upgrade.")
        print()

    # Save the state, create directories if necessary
    _maybe_create_directory(file_path)
    with open(file_path, "w") as file:
        tomlkit.dump(asdict(state), file)


def _maybe_create_directory(file_path: str) -> None:
    marimo_directory = os.path.dirname(file_path)
    if not os.path.exists(marimo_directory):
        os.makedirs(marimo_directory)


def _update_with_latest_version(state: MarimoCLIState) -> MarimoCLIState:
    """
    If we have not saved the latest version,
    or its newer than the one we have, update it.
    """
    pypi_api_url = "https://pypi.org/pypi/marimo/json"

    # Check if a day has passed since the last check
    if state.last_checked_at:
        last_checked_date = datetime.strptime(
            state.last_checked_at, "%Y-%m-%d"
        ).date()
        if (datetime.now().date() - last_checked_date).days < 1:
            # Less than a day has passed, so do nothing
            return state

    # Fetch the latest version from PyPI
    try:
        response = _fetch_data_from_url(pypi_api_url)
        version = response["info"]["version"]
        state.latest_version = version
        state.last_checked_at = datetime.now().strftime("%Y-%m-%d")
        return state
    except Exception:
        # Avoid errors blocking the CLI or adding noise
        return state


def _fetch_data_from_url(url: str) -> Dict[str, Any]:
    with urllib.request.urlopen(url) as response:
        if response.status == 200:
            data = response.read()
            encoding = response.info().get_content_charset("utf-8")
            return json.loads(data.decode(encoding))  # type: ignore
        else:
            raise Exception(
                f"HTTP request failed with status code {response.status}"
            )

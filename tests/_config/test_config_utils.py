# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional
from unittest import mock

from marimo._config.utils import (
    get_or_create_user_config_path,
    get_user_config_path,
)


@contextmanager
def _mock_file_exists(
    exists: Optional[str | list[str]] = None,
    doesnt_exist: Optional[str | list[str]] = None,
):
    if isinstance(exists, str):
        exists = [exists]
    if isinstance(doesnt_exist, str):
        doesnt_exist = [doesnt_exist]

    isfile = os.path.isfile

    def mock_exists(check_path: str) -> bool:
        if (exists is not None) and (check_path in exists):
            return True
        if (doesnt_exist is not None) and (check_path in doesnt_exist):
            return False
        return isfile(check_path)

    with mock.patch(
        "marimo._config.utils.os.path.isfile",
        side_effect=mock_exists,
    ):
        yield


def test_get_config_path():
    xdg_config_path = str(Path("~/.config/marimo/marimo.toml").expanduser())
    home_config_path = str(Path("~/.marimo.toml").expanduser())

    # If neither config exists, return None
    with _mock_file_exists(doesnt_exist=[xdg_config_path, home_config_path]):
        found_config_path = get_user_config_path()
        assert found_config_path is None

    # If only XDG path exists, use XDG path
    with _mock_file_exists(
        exists=xdg_config_path, doesnt_exist=home_config_path
    ):
        found_config_path = get_user_config_path()
        assert found_config_path == xdg_config_path

    # If both config paths exist, home config takes precedence
    with _mock_file_exists(exists=[xdg_config_path, home_config_path]):
        found_config_path = get_user_config_path()
        assert found_config_path == home_config_path


def test_get_or_create_config_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Use temp dir to avoid creating stray xdg config.
        # Still creates home one though, unfortunately.
        os.environ["XDG_CONFIG_HOME"] = temp_dir
        xdg_config_path = str(Path(temp_dir) / "marimo/marimo.toml")
        home_config_path = str(Path("~/.marimo.toml").expanduser())

        # If neither config exists, XDG config should be created and used
        with _mock_file_exists(
            doesnt_exist=[xdg_config_path, home_config_path]
        ):
            found_config_path = get_or_create_user_config_path()
            assert found_config_path == xdg_config_path

        # If only XDG path exists, use XDG path
        with _mock_file_exists(
            exists=xdg_config_path, doesnt_exist=home_config_path
        ):
            found_config_path = get_or_create_user_config_path()
            assert found_config_path == xdg_config_path

        # If both config paths exist, home config takes precedence
        with _mock_file_exists(exists=[xdg_config_path, home_config_path]):
            found_config_path = get_or_create_user_config_path()
            assert found_config_path == home_config_path

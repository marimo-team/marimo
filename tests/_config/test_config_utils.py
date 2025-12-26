# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional
from unittest import mock

import pytest

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

    def mock_path_is_file(self: Path) -> bool:
        return mock_exists(str(self))

    with (
        mock.patch(
            "marimo._config.utils.os.path.isfile",
            side_effect=mock_exists,
        ),
        mock.patch.object(Path, "is_file", mock_path_is_file),
    ):
        yield


def test_get_config_path():
    xdg_config_path = str(Path("~/.config/marimo/marimo.toml").expanduser())
    home_config_path = str(Path("~/.marimo.toml").expanduser())

    get_user_config_path.cache_clear()

    # If neither config exists, return None
    with _mock_file_exists(doesnt_exist=[xdg_config_path, home_config_path]):
        found_config_path = get_user_config_path()
        assert found_config_path is None

    get_user_config_path.cache_clear()

    # If only XDG path exists, use XDG path
    with _mock_file_exists(
        exists=xdg_config_path, doesnt_exist=home_config_path
    ):
        found_config_path = get_user_config_path()
        assert found_config_path == xdg_config_path

    get_user_config_path.cache_clear()

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

        get_user_config_path.cache_clear()

        # If neither config exists, XDG config should be created and used
        with _mock_file_exists(
            doesnt_exist=[xdg_config_path, home_config_path]
        ):
            found_config_path = get_or_create_user_config_path()
            assert found_config_path == xdg_config_path

        get_user_config_path.cache_clear()

        # If only XDG path exists, use XDG path
        with _mock_file_exists(
            exists=xdg_config_path, doesnt_exist=home_config_path
        ):
            found_config_path = get_or_create_user_config_path()
            assert found_config_path == xdg_config_path

        get_user_config_path.cache_clear()

        # If both config paths exist, home config takes precedence
        with _mock_file_exists(exists=[xdg_config_path, home_config_path]):
            found_config_path = get_or_create_user_config_path()
            assert found_config_path == home_config_path


def test_get_or_create_config_path_handles_oserror():
    """Test that get_or_create_user_config_path handles OSError gracefully.

    This can happen on Windows when os.path.realpath(os.getcwd()) fails due to:
    - Deleted directory
    - Permission issues
    - UNC path problems
    - Special characters in path

    See issue #7502
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Use temp dir to avoid creating stray xdg config
        os.environ["XDG_CONFIG_HOME"] = temp_dir
        xdg_config_path = str(Path(temp_dir) / "marimo/marimo.toml")

        get_user_config_path.cache_clear()

        # Mock os.path.realpath to raise OSError (simulating Windows path issue)
        with mock.patch(
            "marimo._config.utils.os.path.realpath",
            side_effect=OSError("Failed to canonicalize path"),
        ):
            # Should handle the error gracefully and return XDG config path
            found_config_path = get_or_create_user_config_path()
            assert found_config_path == xdg_config_path
            # Verify the config file was created
            assert Path(found_config_path).exists()


class TestGetConfigPathParentTraversal:
    """Tests for parent directory traversal in config discovery.

    These tests verify the fix for issue #5825 - marimo should search
    parent directories for .marimo.toml, not just the current directory.

    Test cases are parameterized as (config_locations, cwd, home, expected):
    - config_locations: list of paths (relative to tmpdir) where .marimo.toml exists
    - cwd: current working directory (relative to tmpdir)
    - home: home directory (relative to tmpdir, or absolute path if starts with /)
    - expected: which config should be found (relative to tmpdir), or None
    """

    @pytest.mark.parametrize(
        ("config_locations", "cwd", "home", "expected"),
        [
            pytest.param(
                ["parent"],
                "parent/child",
                "",  # tmpdir is home
                "parent",
                id="config_in_parent_under_home",
            ),
            pytest.param(
                ["grandparent"],
                "grandparent/parent/child",
                "",  # tmpdir is home
                "grandparent",
                id="config_in_grandparent_under_home",
            ),
            pytest.param(
                ["grandparent", "grandparent/parent"],
                "grandparent/parent/child",
                "",  # tmpdir is home
                "grandparent/parent",  # closer config wins
                id="closer_config_takes_precedence",
            ),
            pytest.param(
                ["project"],
                "project/subdir",
                "/home/testuser",  # absolute path, not under tmpdir
                "project",
                id="parent_traversal_outside_home",
            ),
            pytest.param(
                ["opt/project", "home/user"],
                "opt/project/subdir",
                "home/user",
                "opt/project",  # parent traversal before home
                id="disjoint_paths_parent_before_home",
            ),
            pytest.param(
                ["home/user"],
                "opt/project",
                "home/user",
                "home/user",  # falls back to home
                id="falls_back_to_home_when_no_parent_config",
            ),
            pytest.param(
                ["project"],
                "project/subdir",
                "~",  # home expansion fails (service daemon account)
                "project",
                id="home_expansion_fails_still_finds_parent",
            ),
            pytest.param(
                ["", "home/user"],  # config at both root and home
                "home/user/example",
                "home/user",
                "home/user",  # should stop at home, not traverse to root
                id="stops_at_home_ignores_root_config",
            ),
            pytest.param(
                [""],  # config ONLY at root
                "home/user/example",
                "home/user",
                None,  # should NOT find root config when under home
                id="does_not_traverse_past_home_to_root",
            ),
        ],
    )
    def test_config_path_discovery(
        self, tmpdir, config_locations, cwd, home, expected
    ):
        # Create all necessary directories
        cwd_path = tmpdir
        for part in cwd.split("/"):
            cwd_path = (
                cwd_path.mkdir(part)
                if not cwd_path.join(part).exists()
                else cwd_path.join(part)
            )

        # Create config files at specified locations
        for loc in config_locations:
            config_dir = tmpdir
            if loc:  # non-empty path
                for part in loc.split("/"):
                    if not config_dir.join(part).exists():
                        config_dir = config_dir.mkdir(part)
                    else:
                        config_dir = config_dir.join(part)
            config_dir.join(".marimo.toml").write("")

        # Determine home path
        if home == "~":
            home_path = "~"  # simulate failed expansion
        elif home.startswith("/"):
            home_path = home  # absolute path
        elif home == "":
            home_path = str(tmpdir)
        else:
            home_path = str(tmpdir.join(home))

        # Determine expected path
        if expected is None:
            expected_path = None
        else:
            expected_path = str(tmpdir.join(expected).join(".marimo.toml"))

        get_user_config_path.cache_clear()

        with (
            mock.patch(
                "marimo._config.utils.os.getcwd",
                return_value=str(cwd_path),
            ),
            mock.patch(
                "marimo._config.utils.os.path.expanduser",
                return_value=home_path,
            ),
        ):
            found_config_path = get_user_config_path()
            assert found_config_path == expected_path

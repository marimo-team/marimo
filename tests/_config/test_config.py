# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional
from unittest import mock

from marimo._config.config import (
    DEFAULT_CONFIG,
    MarimoConfig,
    mask_secrets,
    merge_config,
    merge_default_config,
    remove_secret_placeholders,
)
from marimo._config.utils import get_config_path, get_or_create_config_path


def assert_config(override: MarimoConfig) -> None:
    user_config = merge_default_config(override)
    assert user_config == {**DEFAULT_CONFIG, **override}


def test_configure_partial_keymap() -> None:
    assert_config(MarimoConfig(keymap={"preset": "vim", "overrides": {}}))


def test_configure_full() -> None:
    assert_config(
        MarimoConfig(
            completion={"activate_on_typing": False, "copilot": False},
            save={
                "autosave": "after_delay",
                "autosave_delay": 2,
                "format_on_save": False,
            },
            keymap={"preset": "vim", "overrides": {}},
            package_management={
                "manager": "pip",
            },
        )
    )


def test_configure_unknown() -> None:
    assert_config({"super cool future config key": {"secret": "value"}})  # type: ignore[typeddict-unknown-key] # noqa: E501


def test_merge_config() -> None:
    prev_config = merge_default_config(
        MarimoConfig(
            ai={
                "open_ai": {
                    "api_key": "super_secret",
                },
                "google": {
                    "api_key": "google_secret",
                },
            },
        )
    )
    assert prev_config["ai"]["open_ai"]["api_key"] == "super_secret"
    assert prev_config["ai"]["google"]["api_key"] == "google_secret"

    new_config = merge_config(
        prev_config,
        MarimoConfig(
            ai={
                "open_ai": {
                    "model": "davinci",
                },
                "google": {
                    "model": "gemini-1.5-pro",
                },
            },
        ),
    )

    assert new_config["ai"]["open_ai"]["api_key"] == "super_secret"
    assert new_config["ai"]["open_ai"]["model"] == "davinci"
    assert new_config["ai"]["google"]["api_key"] == "google_secret"
    assert new_config["ai"]["google"]["model"] == "gemini-1.5-pro"


def test_merge_config_with_keymap_overrides() -> None:
    prev_config = merge_default_config(
        MarimoConfig(
            keymap={
                "preset": "default",
                "overrides": {
                    "run-all": "ctrl-enter",
                },
            },
        )
    )
    assert prev_config["keymap"]["preset"] == "default"
    assert prev_config["keymap"]["overrides"]["run-all"] == "ctrl-enter"

    new_config = merge_config(
        prev_config,
        MarimoConfig(
            keymap={
                "preset": "vim",
                "overrides": {
                    "run-cell": "ctrl-enter",
                },
            },
        ),
    )

    assert new_config["keymap"]["preset"] == "vim"
    assert "run-all" not in new_config["keymap"]["overrides"]
    assert new_config["keymap"]["overrides"]["run-cell"] == "ctrl-enter"

    new_config = merge_config(
        prev_config,
        MarimoConfig(
            keymap={
                "preset": "vim",
                "overrides": {},
            },
        ),
    )

    assert new_config["keymap"]["preset"] == "vim"
    assert new_config["keymap"]["overrides"] == {}


def test_mask_secrets() -> None:
    config = MarimoConfig(
        ai={
            "open_ai": {"api_key": "super_secret"},
            "anthropic": {"api_key": "anthropic_secret"},
            "google": {"api_key": "google_secret"},
        }
    )
    assert config["ai"]["open_ai"]["api_key"] == "super_secret"
    assert config["ai"]["anthropic"]["api_key"] == "anthropic_secret"
    assert config["ai"]["google"]["api_key"] == "google_secret"

    new_config = mask_secrets(config)
    assert new_config["ai"]["open_ai"]["api_key"] == "********"
    assert new_config["ai"]["anthropic"]["api_key"] == "********"
    assert new_config["ai"]["google"]["api_key"] == "********"

    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["api_key"] == "super_secret"
    assert config["ai"]["anthropic"]["api_key"] == "anthropic_secret"
    assert config["ai"]["google"]["api_key"] == "google_secret"


def test_mask_secrets_empty() -> None:
    config = MarimoConfig(
        ai={
            "open_ai": {"model": "davinci"},
            "google": {},
            "anthropic": {},
        }
    )
    assert config["ai"]["open_ai"]["model"] == "davinci"

    new_config = mask_secrets(config)
    assert new_config["ai"]["open_ai"]["model"] == "davinci"
    # Not added until the key is present
    assert "api_key" not in new_config["ai"]["open_ai"]
    assert "api_key" not in new_config["ai"]["google"]
    assert "api_key" not in new_config["ai"]["anthropic"]
    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["model"] == "davinci"

    # Not added when key is ""
    config["ai"]["open_ai"]["api_key"] = ""
    config["ai"]["google"]["api_key"] = ""
    config["ai"]["anthropic"]["api_key"] = ""
    new_config = mask_secrets(config)
    assert new_config["ai"]["open_ai"]["api_key"] == ""
    assert new_config["ai"]["google"]["api_key"] == ""
    assert new_config["ai"]["anthropic"]["api_key"] == ""
    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["api_key"] == ""
    assert config["ai"]["google"]["api_key"] == ""
    assert config["ai"]["anthropic"]["api_key"] == ""


def test_remove_secret_placeholders() -> None:
    config = MarimoConfig(
        ai={
            "open_ai": {"api_key": "********"},
            "google": {"api_key": "********"},
            "anthropic": {"api_key": "********"},
        }
    )
    assert config["ai"]["open_ai"]["api_key"] == "********"
    assert config["ai"]["google"]["api_key"] == "********"
    assert config["ai"]["anthropic"]["api_key"] == "********"
    new_config = remove_secret_placeholders(config)
    assert "api_key" not in new_config["ai"]["open_ai"]
    assert "api_key" not in new_config["ai"]["google"]
    assert "api_key" not in new_config["ai"]["anthropic"]
    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["api_key"] == "********"
    assert config["ai"]["google"]["api_key"] == "********"
    assert config["ai"]["anthropic"]["api_key"] == "********"


@contextmanager
def _mock_file_exists(
    exists: Optional[str | List[str]] = None,
    doesnt_exist: Optional[str | List[str]] = None,
):
    if isinstance(exists, str):
        exists = [exists]
    if isinstance(doesnt_exist, str):
        doesnt_exist = [doesnt_exist]

    isfile = os.path.isfile

    def mock_exists(check_path):
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
        found_config_path = get_config_path()
        assert found_config_path is None

    # If only XDG path exists, use XDG path
    with _mock_file_exists(
        exists=xdg_config_path, doesnt_exist=home_config_path
    ):
        found_config_path = get_config_path()
        assert found_config_path == xdg_config_path

    # If both config paths exist, home config takes precedence
    with _mock_file_exists(exists=[xdg_config_path, home_config_path]):
        found_config_path = get_config_path()
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
            found_config_path = get_or_create_config_path()
            assert found_config_path == xdg_config_path

        # If only XDG path exists, use XDG path
        with _mock_file_exists(
            exists=xdg_config_path, doesnt_exist=home_config_path
        ):
            found_config_path = get_or_create_config_path()
            assert found_config_path == xdg_config_path

        # If both config paths exist, home config takes precedence
        with _mock_file_exists(exists=[xdg_config_path, home_config_path]):
            found_config_path = get_or_create_config_path()
            assert found_config_path == home_config_path

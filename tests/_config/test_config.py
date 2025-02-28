# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Union

from marimo._config.config import (
    DEFAULT_CONFIG,
    MarimoConfig,
    PartialMarimoConfig,
    merge_config,
    merge_default_config,
)


def assert_config(override: Union[MarimoConfig, PartialMarimoConfig]) -> None:
    user_config = merge_default_config(override)
    assert user_config == {**DEFAULT_CONFIG, **override}


def test_configure_partial_keymap() -> None:
    assert_config(
        PartialMarimoConfig(keymap={"preset": "vim", "overrides": {}})
    )


def test_configure_full() -> None:
    assert_config(
        PartialMarimoConfig(
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
        PartialMarimoConfig(
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
        PartialMarimoConfig(
            ai={
                "open_ai": {
                    "model": "davinci",
                },
                "google": {
                    "api_key": "google_secret",
                },
            },
        ),
    )

    assert new_config["ai"]["open_ai"]["api_key"] == "super_secret"
    assert new_config["ai"]["open_ai"]["model"] == "davinci"
    assert new_config["ai"]["google"]["api_key"] == "google_secret"


def test_merge_config_with_keymap_overrides() -> None:
    prev_config = merge_default_config(
        PartialMarimoConfig(
            keymap={
                "preset": "default",
                "overrides": {
                    "run-all": "ctrl-enter",
                },
            },
        )
    )
    assert "preset" in prev_config["keymap"]
    assert "overrides" in prev_config["keymap"]
    assert prev_config["keymap"]["preset"] == "default"
    assert prev_config["keymap"]["overrides"]["run-all"] == "ctrl-enter"

    new_config = merge_config(
        prev_config,
        PartialMarimoConfig(
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
        PartialMarimoConfig(
            keymap={
                "preset": "vim",
                "overrides": {},
            },
        ),
    )

    assert new_config["keymap"]["preset"] == "vim"
    assert new_config["keymap"]["overrides"] == {}


def test_marimo_config_rtc_disabled() -> None:
    config = merge_default_config(
        PartialMarimoConfig(experimental={"rtc": True})
    )
    assert "experimental" in config
    assert not config["experimental"]["rtc"]

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
            completion={
                "activate_on_typing": False,
                "copilot": False,
                "signature_hint_on_typing": False,
            },
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
    assert (
        prev_config.get("ai", {}).get("open_ai", {}).get("api_key")
        == "super_secret"
    )
    assert (
        prev_config.get("ai", {}).get("google", {}).get("api_key")
        == "google_secret"
    )

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

    assert (
        new_config.get("ai", {}).get("open_ai", {}).get("api_key")
        == "super_secret"
    )
    assert (
        new_config.get("ai", {}).get("open_ai", {}).get("model") == "davinci"
    )
    assert (
        new_config.get("ai", {}).get("google", {}).get("api_key")
        == "google_secret"
    )


def test_configure_github_with_copilot_settings() -> None:
    """Test GitHub AI configuration with copilot_settings."""
    config = merge_default_config(
        PartialMarimoConfig(
            ai={
                "github": {
                    "api_key": "test-github-key",
                    "copilot_settings": {
                        "http": {
                            "proxy": "http://proxy.example.com:8888",
                            "proxyStrictSSL": True,
                        },
                        "telemetry": {"telemetryLevel": "off"},
                        "github-enterprise": {
                            "uri": "https://github.enterprise.com"
                        },
                    },
                }
            }
        )
    )

    github_config = config.get("ai", {}).get("github", {})
    assert github_config.get("api_key") == "test-github-key"
    assert github_config.get("copilot_settings") is not None
    copilot_settings = github_config.get("copilot_settings", {})
    assert (
        copilot_settings.get("http", {}).get("proxy")
        == "http://proxy.example.com:8888"
    )
    assert copilot_settings.get("http", {}).get("proxyStrictSSL") is True
    assert copilot_settings.get("telemetry", {}).get("telemetryLevel") == "off"
    assert (
        copilot_settings.get("github-enterprise", {}).get("uri")
        == "https://github.enterprise.com"
    )


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
    assert "run-all" not in new_config.get("keymap", {}).get("overrides", {})
    assert (
        new_config.get("keymap", {}).get("overrides", {}).get("run-cell")
        == "ctrl-enter"
    )

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
    assert new_config.get("keymap", {}).get("overrides", {}) == {}

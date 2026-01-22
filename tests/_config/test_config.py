# Copyright 2026 Marimo. All rights reserved.
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


def test_merge_config_custom_providers_replaces_instead_of_merging() -> None:
    """Test that custom_providers is replaced, not merged.

    This is important because users can add/remove custom providers,
    and we want the new config to completely replace the old one.
    """
    prev_config = merge_default_config(
        PartialMarimoConfig(
            ai={
                "custom_providers": {
                    "provider1": {
                        "api_key": "key1",
                        "base_url": "https://api1.example.com",
                    },
                    "provider2": {
                        "api_key": "key2",
                        "base_url": "https://api2.example.com",
                    },
                },
            },
        )
    )

    # Verify initial state
    custom_providers = prev_config.get("ai", {}).get("custom_providers", {})
    assert "provider1" in custom_providers
    assert "provider2" in custom_providers

    # Update with only provider1 (removing provider2)
    new_config = merge_config(
        prev_config,
        PartialMarimoConfig(
            ai={
                "custom_providers": {
                    "provider1": {
                        "api_key": "key1_updated",
                        "base_url": "https://api1.example.com",
                    },
                    # provider2 is intentionally removed
                },
            },
        ),
    )

    # provider2 should be gone (replaced, not merged)
    new_custom_providers = new_config.get("ai", {}).get("custom_providers", {})
    assert "provider1" in new_custom_providers
    assert "provider2" not in new_custom_providers
    assert new_custom_providers["provider1"]["api_key"] == "key1_updated"


def test_merge_config_custom_providers_can_be_emptied() -> None:
    """Test that custom_providers can be set to empty dict."""
    prev_config = merge_default_config(
        PartialMarimoConfig(
            ai={
                "custom_providers": {
                    "provider1": {
                        "api_key": "key1",
                        "base_url": "https://api1.example.com",
                    },
                },
            },
        )
    )

    # Update with empty custom_providers
    new_config = merge_config(
        prev_config,
        PartialMarimoConfig(
            ai={
                "custom_providers": {},
            },
        ),
    )

    # custom_providers should be empty
    assert new_config.get("ai", {}).get("custom_providers", {}) == {}


def test_merge_config_custom_providers_preserves_other_ai_settings() -> None:
    """Test that updating custom_providers doesn't affect other AI settings."""
    prev_config = merge_default_config(
        PartialMarimoConfig(
            ai={
                "open_ai": {
                    "api_key": "openai_key",
                },
                "custom_providers": {
                    "provider1": {
                        "api_key": "key1",
                        "base_url": "https://api1.example.com",
                    },
                },
            },
        )
    )

    # Update only custom_providers
    new_config = merge_config(
        prev_config,
        PartialMarimoConfig(
            ai={
                "custom_providers": {
                    "provider2": {
                        "api_key": "key2",
                        "base_url": "https://api2.example.com",
                    },
                },
            },
        ),
    )

    # OpenAI config should be preserved
    assert (
        new_config.get("ai", {}).get("open_ai", {}).get("api_key")
        == "openai_key"
    )
    # custom_providers should be replaced
    custom_providers = new_config.get("ai", {}).get("custom_providers", {})
    assert "provider1" not in custom_providers
    assert "provider2" in custom_providers


def test_merge_config_custom_providers_partial_update_preserves_fields() -> (
    None
):
    """Test that updating one field of a provider preserves other fields.

    This validates the merge-replace behavior: when updating only base_url,
    the api_key should be preserved (not lost due to replacement).
    """
    prev_config = merge_default_config(
        PartialMarimoConfig(
            ai={
                "custom_providers": {
                    "provider1": {
                        "api_key": "secret_key",
                        "base_url": "https://old.example.com",
                    },
                },
            },
        )
    )

    # Update only base_url (simulates getDirtyValues sending partial update)
    new_config = merge_config(
        prev_config,
        PartialMarimoConfig(
            ai={
                "custom_providers": {
                    "provider1": {
                        "base_url": "https://new.example.com",
                    },
                },
            },
        ),
    )

    # api_key should be preserved, base_url should be updated
    provider1 = (
        new_config.get("ai", {})
        .get("custom_providers", {})
        .get("provider1", {})
    )
    assert provider1.get("api_key") == "secret_key", (
        "api_key should be preserved"
    )
    assert provider1.get("base_url") == "https://new.example.com", (
        "base_url should be updated"
    )

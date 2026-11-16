# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import copy

import pytest

from marimo._config.config import (
    DEFAULT_CONFIG,
    PartialMarimoConfig,
    merge_config,
    merge_default_config,
    parse_config,
)
from marimo._config.config_schema import MarimoConfig


@pytest.mark.parametrize("malformed", [None, "invalid", {}, {"path": 123}])
def test_parse_config_preserves_valid_file_browser_folders(
    malformed: object,
) -> None:
    values = {
        "file_browser": {
            "folders": [
                {"path": "/first", "name": "First"},
                malformed,
                {"path": "/last"},
                malformed,
            ]
        }
    }
    original = copy.deepcopy(values)

    resolved = parse_config(values)

    assert resolved.file_browser is not None
    assert resolved.file_browser.to_dict() == {
        "folders": [
            {"path": "/first", "name": "First"},
            {"path": "/last", "name": None},
        ]
    }
    assert values == original


@pytest.mark.parametrize(
    "malformed",
    [
        None,
        {},
        {"command": 123},
        {"command": "python", "args": [123]},
        {"url": 123},
    ],
)
def test_parse_config_preserves_valid_mcp_servers(malformed: object) -> None:
    servers = {
        "stdio": {"command": "python", "args": ["server.py"]},
        "http": {"url": "https://example.com/mcp"},
        "invalid": malformed,
    }
    values = {"mcp": {"mcpServers": servers, "presets": ["marimo"]}}
    original = copy.deepcopy(values)

    resolved = parse_config(values)

    assert resolved.mcp.to_dict() == {
        "mcpServers": {"stdio": servers["stdio"], "http": servers["http"]},
        "presets": ["marimo"],
    }
    assert values == original


def assert_config(override: MarimoConfig | PartialMarimoConfig) -> None:
    user_config = (merge_default_config(override)).to_dict()
    assert user_config == {
        **DEFAULT_CONFIG.to_dict(),
        **(
            override.to_dict()
            if isinstance(override, MarimoConfig)
            else override
        ),
    }


def test_allow_provider_config_defaults_true() -> None:
    assert DEFAULT_CONFIG.to_dict()["ai"]["allow_provider_config"] is True


def test_allow_provider_config_can_be_disabled() -> None:
    merged = (
        merge_default_config(
            PartialMarimoConfig(ai={"allow_provider_config": False})
        )
    ).to_dict()
    assert merged["ai"]["allow_provider_config"] is False


def test_configure_partial_keymap() -> None:
    assert_config(
        PartialMarimoConfig(keymap={"preset": "vim", "overrides": {}})
    )


def test_configure_file_browser_folders() -> None:
    assert_config(
        PartialMarimoConfig(
            file_browser={
                "folders": [
                    {"path": "/data", "name": "Data"},
                    {"path": "/shared", "name": None},
                ]
            }
        )
    )


def test_configure_full() -> None:
    assert_config(
        PartialMarimoConfig(
            completion={
                "activate_on_typing": False,
                "auto_close_pairs": True,
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
    assert_config({"super cool future config key": {"secret": "value"}})  # type: ignore[typeddict-unknown-key]


def test_merge_config() -> None:
    prev_config = (
        merge_default_config(
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
    ).to_dict()
    assert (
        prev_config.get("ai", {}).get("open_ai", {}).get("api_key")
        == "super_secret"
    )
    assert (
        prev_config.get("ai", {}).get("google", {}).get("api_key")
        == "google_secret"
    )

    new_config = (
        merge_config(
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
    ).to_dict()

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
    config = (
        merge_default_config(
            PartialMarimoConfig(
                ai={
                    "github": {
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
    ).to_dict()

    github_config = config.get("ai", {}).get("github", {})
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
    prev_config = (
        merge_default_config(
            PartialMarimoConfig(
                keymap={
                    "preset": "default",
                    "overrides": {
                        "run-all": "ctrl-enter",
                    },
                },
            )
        )
    ).to_dict()
    assert "preset" in prev_config["keymap"]
    assert "overrides" in prev_config["keymap"]
    assert prev_config["keymap"]["preset"] == "default"
    assert prev_config["keymap"]["overrides"]["run-all"] == "ctrl-enter"

    new_config = (
        merge_config(
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
    ).to_dict()

    assert new_config["keymap"]["preset"] == "vim"
    assert "run-all" not in new_config.get("keymap", {}).get("overrides", {})
    assert (
        new_config.get("keymap", {}).get("overrides", {}).get("run-cell")
        == "ctrl-enter"
    )

    new_config = (
        merge_config(
            prev_config,
            PartialMarimoConfig(
                keymap={
                    "preset": "vim",
                    "overrides": {},
                },
            ),
        )
    ).to_dict()

    assert new_config["keymap"]["preset"] == "vim"
    assert new_config.get("keymap", {}).get("overrides", {}) == {}


def test_merge_config_custom_providers_replaces_instead_of_merging() -> None:
    """Test that custom_providers is replaced, not merged.

    This is important because users can add/remove custom providers,
    and we want the new config to completely replace the old one.
    """
    prev_config = (
        merge_default_config(
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
    ).to_dict()

    # Verify initial state
    custom_providers = prev_config.get("ai", {}).get("custom_providers", {})
    assert "provider1" in custom_providers
    assert "provider2" in custom_providers

    # Update with only provider1 (removing provider2)
    new_config = (
        merge_config(
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
    ).to_dict()

    # provider2 should be gone (replaced, not merged)
    new_custom_providers = new_config.get("ai", {}).get("custom_providers", {})
    assert "provider1" in new_custom_providers
    assert "provider2" not in new_custom_providers
    assert new_custom_providers["provider1"].get("api_key") == "key1_updated"


def test_merge_config_custom_providers_can_be_emptied() -> None:
    """Test that custom_providers can be set to empty dict."""
    prev_config = (
        merge_default_config(
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
    ).to_dict()

    # Update with empty custom_providers
    new_config = (
        merge_config(
            prev_config,
            PartialMarimoConfig(
                ai={
                    "custom_providers": {},
                },
            ),
        )
    ).to_dict()

    # custom_providers should be empty
    assert new_config.get("ai", {}).get("custom_providers", {}) == {}


def test_merge_config_trusted_signers_replaces_for_revocation() -> None:
    """signing.trusted_signers is replaced, not merged, so a higher-priority
    layer can narrow or revoke trust (a deep merge would union the keys and make
    revocation impossible)."""
    fp_a = "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA0"
    fp_b = "SHA256:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB0"
    prev_config = (
        merge_default_config(
            PartialMarimoConfig(
                signing={"trusted_signers": {fp_a: "a", fp_b: "b"}}
            )
        )
    ).to_dict()

    # A higher-priority layer keeps only fp_a.
    new_config = (
        merge_config(
            prev_config,
            PartialMarimoConfig(signing={"trusted_signers": {fp_a: "a"}}),
        )
    ).to_dict()
    trusted = new_config.get("signing", {}).get("trusted_signers", {})
    assert fp_a in trusted
    assert fp_b not in trusted

    # And an empty map revokes all trust.
    emptied = (
        merge_config(
            prev_config,
            PartialMarimoConfig(signing={"trusted_signers": {}}),
        )
    ).to_dict()
    assert emptied.get("signing", {}).get("trusted_signers", {}) == {}


def test_merge_config_custom_providers_preserves_other_ai_settings() -> None:
    """Test that updating custom_providers doesn't affect other AI settings."""
    prev_config = (
        merge_default_config(
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
    ).to_dict()

    # Update only custom_providers
    new_config = (
        merge_config(
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
    ).to_dict()

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
    prev_config = (
        merge_default_config(
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
    ).to_dict()

    # Update only base_url (simulates getDirtyValues sending partial update)
    new_config = (
        merge_config(
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
    ).to_dict()

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


def test_merge_config_custom_providers_partial_update_api_key_preserves_base_url() -> (
    None
):
    """Test that updating api_key preserves base_url (inverse of above test)."""
    prev_config = (
        merge_default_config(
            PartialMarimoConfig(
                ai={
                    "custom_providers": {
                        "provider1": {
                            "api_key": "old_key",
                            "base_url": "https://api.example.com",
                        },
                    },
                },
            )
        )
    ).to_dict()

    # Update only api_key
    new_config = (
        merge_config(
            prev_config,
            PartialMarimoConfig(
                ai={
                    "custom_providers": {
                        "provider1": {
                            "api_key": "new_key",
                        },
                    },
                },
            ),
        )
    ).to_dict()

    provider1 = (
        new_config.get("ai", {})
        .get("custom_providers", {})
        .get("provider1", {})
    )
    assert provider1.get("api_key") == "new_key", "api_key should be updated"
    assert provider1.get("base_url") == "https://api.example.com", (
        "base_url should be preserved"
    )


def test_merge_config_custom_providers_add_new_keeps_existing() -> None:
    """Test that adding a new provider preserves existing providers."""
    prev_config = (
        merge_default_config(
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
    ).to_dict()

    # Add provider2 while keeping provider1
    new_config = (
        merge_config(
            prev_config,
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
            ),
        )
    ).to_dict()

    custom_providers = new_config.get("ai", {}).get("custom_providers", {})
    assert "provider1" in custom_providers, "provider1 should still exist"
    assert "provider2" in custom_providers, "provider2 should be added"
    assert custom_providers["provider1"].get("api_key") == "key1"
    assert custom_providers["provider2"].get("api_key") == "key2"


def test_merge_config_custom_providers_update_one_preserves_others() -> None:
    """Test that updating one provider doesn't affect other providers."""
    prev_config = (
        merge_default_config(
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
    ).to_dict()

    # Update only provider1's base_url, provider2 included unchanged
    new_config = (
        merge_config(
            prev_config,
            PartialMarimoConfig(
                ai={
                    "custom_providers": {
                        "provider1": {
                            "base_url": "https://new-api1.example.com",
                        },
                        "provider2": {
                            "api_key": "key2",
                            "base_url": "https://api2.example.com",
                        },
                    },
                },
            ),
        )
    ).to_dict()

    custom_providers = new_config.get("ai", {}).get("custom_providers", {})

    # provider1 should have updated base_url but preserved api_key
    assert custom_providers["provider1"].get("api_key") == "key1", (
        "provider1 api_key should be preserved"
    )
    assert custom_providers["provider1"].get("base_url") == (
        "https://new-api1.example.com"
    ), "provider1 base_url should be updated"

    # provider2 should be completely unchanged
    assert custom_providers["provider2"].get("api_key") == "key2", (
        "provider2 should be unchanged"
    )
    assert custom_providers["provider2"].get("base_url") == (
        "https://api2.example.com"
    ), "provider2 should be unchanged"

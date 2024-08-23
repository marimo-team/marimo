# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._config.config import (
    DEFAULT_CONFIG,
    MarimoConfig,
    mask_secrets,
    merge_config,
    merge_default_config,
    remove_secret_placeholders,
)


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
                "add_script_metadata": False,
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
                }
            },
        )
    )
    assert prev_config["ai"]["open_ai"]["api_key"] == "super_secret"

    new_config = merge_config(
        prev_config,
        MarimoConfig(
            ai={
                "open_ai": {
                    "model": "davinci",
                }
            },
        ),
    )

    assert new_config["ai"]["open_ai"]["api_key"] == "super_secret"
    assert new_config["ai"]["open_ai"]["model"] == "davinci"


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
    config = MarimoConfig(ai={"open_ai": {"api_key": "super_secret"}})
    assert config["ai"]["open_ai"]["api_key"] == "super_secret"

    new_config = mask_secrets(config)
    assert new_config["ai"]["open_ai"]["api_key"] == "********"

    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["api_key"] == "super_secret"


def test_mask_secrets_empty() -> None:
    config = MarimoConfig(ai={"open_ai": {"model": "davinci"}})
    assert config["ai"]["open_ai"]["model"] == "davinci"

    new_config = mask_secrets(config)
    assert new_config["ai"]["open_ai"]["model"] == "davinci"
    # Not added until the key is present
    assert "api_key" not in new_config["ai"]["open_ai"]

    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["model"] == "davinci"

    # Not added when key is ""
    config["ai"]["open_ai"]["api_key"] = ""
    new_config = mask_secrets(config)
    assert new_config["ai"]["open_ai"]["api_key"] == ""
    assert config["ai"]["open_ai"]["api_key"] == ""


def test_remove_secret_placeholders() -> None:
    config = MarimoConfig(ai={"open_ai": {"api_key": "********"}})
    assert config["ai"]["open_ai"]["api_key"] == "********"

    new_config = remove_secret_placeholders(config)
    assert "api_key" not in new_config["ai"]["open_ai"]

    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["api_key"] == "********"

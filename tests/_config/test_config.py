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


def test_merge_config_openai_model_fallback() -> None:
    """Test that openai_model is used as fallback for missing chat_model and edit_model."""
    base_config = merge_default_config(PartialMarimoConfig())

    new_config = merge_config(
        base_config,
        PartialMarimoConfig(
            ai={
                "open_ai": {
                    "api_key": "test_key",
                    "model": "gpt-4",
                },
            }
        ),
    )

    # When neither chat_model nor edit_model are present, openai_model should be used for both
    assert new_config["ai"]["models"]["chat_model"] == "gpt-4"
    assert new_config["ai"]["models"]["edit_model"] == "gpt-4"
    assert new_config["ai"]["open_ai"]["model"] == "gpt-4"


def test_merge_config_existing_chat_edit_models_no_fallback() -> None:
    """Test that existing chat_model and edit_model are preserved (no fallback)."""
    base_config = merge_default_config(PartialMarimoConfig())

    new_config = merge_config(
        base_config,
        PartialMarimoConfig(
            ai={
                "open_ai": {
                    "api_key": "test_key",
                    "model": "gpt-4",
                },
                "models": {
                    "chat_model": "claude-3-sonnet",
                    "edit_model": "gpt-3.5-turbo",
                    "enabled_models": [],
                    "custom_models": [],
                },
            }
        ),
    )

    # Existing models should be preserved, not overridden by openai_model
    assert new_config["ai"]["models"]["chat_model"] == "claude-3-sonnet"
    assert new_config["ai"]["models"]["edit_model"] == "gpt-3.5-turbo"
    assert new_config["ai"]["open_ai"]["model"] == "gpt-4"


def test_merge_config_no_openai_model_no_fallback() -> None:
    """Test that no fallback happens when openai_model is not present."""
    base_config = merge_default_config(PartialMarimoConfig())

    new_config = merge_config(
        base_config,
        PartialMarimoConfig(
            ai={
                "open_ai": {
                    "api_key": "test_key",
                },
            }
        ),
    )

    # No models should be set since openai_model is not present
    assert "chat_model" not in new_config["ai"]["models"]
    assert "edit_model" not in new_config["ai"]["models"]


def test_merge_config_partial_model_config() -> None:
    """Test fallback when only one of chat_model or edit_model is present."""
    base_config = merge_default_config(PartialMarimoConfig())

    # Test with only chat_model present
    new_config = merge_config(
        base_config,
        PartialMarimoConfig(
            ai={
                "open_ai": {
                    "api_key": "test_key",
                    "model": "gpt-4",
                },
                "models": {
                    "chat_model": "claude-3-sonnet",
                    "enabled_models": [],
                    "custom_models": [],
                },
            }
        ),
    )

    # chat_model should be preserved, but no fallback should happen since chat_model exists
    assert new_config["ai"]["models"]["chat_model"] == "claude-3-sonnet"
    assert "edit_model" not in new_config["ai"]["models"]

    # Test with only edit_model present
    new_config = merge_config(
        base_config,
        PartialMarimoConfig(
            ai={
                "open_ai": {
                    "api_key": "test_key",
                    "model": "gpt-4",
                },
                "models": {
                    "edit_model": "gpt-3.5-turbo",
                    "enabled_models": [],
                    "custom_models": [],
                },
            }
        ),
    )

    # edit_model should be preserved, but no fallback should happen since edit_model exists
    assert new_config["ai"]["models"]["edit_model"] == "gpt-3.5-turbo"
    assert "chat_model" not in new_config["ai"]["models"]


def test_merge_config_empty_models_with_openai_model() -> None:
    """Test fallback when models config exists but chat_model and edit_model are empty/None."""
    base_config = merge_default_config(PartialMarimoConfig())

    new_config = merge_config(
        base_config,
        PartialMarimoConfig(
            ai={
                "open_ai": {
                    "api_key": "test_key",
                    "model": "gpt-4",
                },
                "models": {
                    "chat_model": None,
                    "edit_model": "",
                    "enabled_models": [],
                    "custom_models": [],
                },
            }
        ),
    )

    # Empty/None values should trigger fallback to openai_model
    assert new_config["ai"]["models"]["chat_model"] == "gpt-4"
    assert new_config["ai"]["models"]["edit_model"] == "gpt-4"

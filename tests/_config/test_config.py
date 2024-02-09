# Copyright 2024 Marimo. All rights reserved.
from marimo._config.config import DEFAULT_CONFIG, MarimoConfig, merge_config


def assert_config(override: MarimoConfig) -> None:
    user_config = merge_config(override)
    assert user_config == {**DEFAULT_CONFIG, **override}


def test_configure_partial_keymap() -> None:
    assert_config(MarimoConfig(keymap={"preset": "vim"}))


def test_configure_full() -> None:
    assert_config(
        MarimoConfig(
            completion={"activate_on_typing": False, "copilot": False},
            save={
                "autosave": "after_delay",
                "autosave_delay": 2,
                "format_on_save": False,
            },
            keymap={"preset": "vim"},
        )
    )


def test_configure_unknown() -> None:
    assert_config({"super cool future config key": {"secret": "value"}})  # type: ignore[typeddict-unknown-key] # noqa: E501

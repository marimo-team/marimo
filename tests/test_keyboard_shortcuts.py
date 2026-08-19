from __future__ import annotations

from unittest.mock import patch

from marimo._entrypoints.keyboard_shortcuts import load_keyboard_shortcuts
from marimo._entrypoints.registry import EntryPointRegistry


def test_load_keyboard_shortcuts_namespaces_plain_metadata() -> None:
    registry = EntryPointRegistry[object]("marimo.keyboard_shortcuts")
    registry.register(
        "companion",
        {
            "show-message": {
                "name": "Show companion message",
                "key": "Mod-Shift-Y",
                "additional_keywords": ["companion", "extension"],
            }
        },
    )

    with patch(
        "marimo._entrypoints.registry.get_entry_points", return_value=[]
    ):
        assert load_keyboard_shortcuts(registry) == {
            "extension.companion.show-message": {
                "name": "Show companion message",
                "key": "Mod-Shift-Y",
                "group": "Other",
                "additionalKeywords": ["companion", "extension"],
            }
        }


def test_load_keyboard_shortcuts_skips_invalid_provider() -> None:
    registry = EntryPointRegistry[object]("marimo.keyboard_shortcuts")
    registry.register(
        "invalid",
        {"show-message": {"name": "Show message", "key": ""}},
    )
    registry.register(
        "valid",
        {"run-tool": {"name": "Run tool", "key": "Alt-T"}},
    )

    with patch(
        "marimo._entrypoints.registry.get_entry_points", return_value=[]
    ):
        assert load_keyboard_shortcuts(registry) == {
            "extension.valid.run-tool": {
                "name": "Run tool",
                "key": "Alt-T",
                "group": "Other",
                "additionalKeywords": [],
            }
        }

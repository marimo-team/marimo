from __future__ import annotations

from unittest.mock import patch

from marimo._entrypoints import keyboard_shortcuts
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


def test_load_keyboard_shortcuts_skips_invalid_shortcuts() -> None:
    registry = EntryPointRegistry[object]("marimo.keyboard_shortcuts")
    registry.register(
        "companion",
        {
            "show-message": {"name": "Show message", "key": ""},
            "open-tool": {
                "name": "Open tool",
                "key": "Alt-O",
                "unknown": True,
            },
            "run-tool": {"name": "Run tool", "key": "Alt-T"},
        },
    )

    with patch(
        "marimo._entrypoints.registry.get_entry_points", return_value=[]
    ):
        assert load_keyboard_shortcuts(registry) == {
            "extension.companion.run-tool": {
                "name": "Run tool",
                "key": "Alt-T",
                "group": "Other",
                "additionalKeywords": [],
            }
        }


def test_load_keyboard_shortcuts_caches_independent_results() -> None:
    registry = EntryPointRegistry[object]("marimo.keyboard_shortcuts")
    registry.register(
        "companion",
        {
            "run-tool": {
                "name": "Run tool",
                "key": "Alt-T",
                "additional_keywords": ["companion"],
            }
        },
    )

    with (
        patch.object(keyboard_shortcuts, "_REGISTRY", registry),
        patch.object(registry, "names", wraps=registry.names) as names,
        patch(
            "marimo._entrypoints.registry.get_entry_points", return_value=[]
        ),
    ):
        shortcuts = keyboard_shortcuts.load_keyboard_shortcuts()
        shortcut = shortcuts["extension.companion.run-tool"]
        shortcut["name"] = "Changed"
        shortcut["additionalKeywords"].append("changed")

        assert keyboard_shortcuts.load_keyboard_shortcuts() == {
            "extension.companion.run-tool": {
                "name": "Run tool",
                "key": "Alt-T",
                "group": "Other",
                "additionalKeywords": ["companion"],
            }
        }

    names.assert_called_once_with()


def test_load_keyboard_shortcuts_does_not_cache_custom_registry() -> None:
    registry = EntryPointRegistry[object]("marimo.keyboard_shortcuts")

    with patch(
        "marimo._entrypoints.registry.get_entry_points", return_value=[]
    ):
        assert load_keyboard_shortcuts(registry) == {}

        registry.register(
            "companion",
            {"run-tool": {"name": "Run tool", "key": "Alt-T"}},
        )
        assert load_keyboard_shortcuts(registry) == {
            "extension.companion.run-tool": {
                "name": "Run tool",
                "key": "Alt-T",
                "group": "Other",
                "additionalKeywords": [],
            }
        }

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal, TypeAlias, TypedDict

import msgspec

from marimo import _loggers
from marimo._entrypoints.registry import EntryPointRegistry

HotkeyGroup = Literal[
    "Running Cells",
    "Creation and Ordering",
    "Navigation",
    "Editing",
    "Markdown",
    "Command",
    "Other",
]


class KeyboardShortcut(TypedDict):
    name: str
    key: str
    group: HotkeyGroup
    additionalKeywords: list[str]


KeyboardShortcuts: TypeAlias = dict[str, KeyboardShortcut]


class _ShortcutMetadata(msgspec.Struct, forbid_unknown_fields=True):
    name: str
    key: str
    group: HotkeyGroup = "Other"
    additional_keywords: list[str] = msgspec.field(default_factory=list)


_REGISTRY = EntryPointRegistry[object]("marimo.keyboard_shortcuts")
LOGGER = _loggers.marimo_logger()


def load_keyboard_shortcuts(
    registry: EntryPointRegistry[object] = _REGISTRY,
) -> KeyboardShortcuts:
    """Load keyboard shortcut metadata from installed packages."""
    shortcuts: KeyboardShortcuts = {}

    for provider in registry.names():
        try:
            metadata = msgspec.convert(
                registry.get(provider),
                type=dict[str, _ShortcutMetadata],
                strict=True,
            )
            loaded: KeyboardShortcuts = {}
            for shortcut_id, shortcut in metadata.items():
                if not shortcut_id.strip():
                    raise ValueError("shortcut IDs must not be empty")
                if not shortcut.name.strip():
                    raise ValueError("shortcut names must not be empty")
                if not shortcut.key.strip():
                    raise ValueError("shortcut keys must not be empty")

                action = f"extension.{provider}.{shortcut_id}"
                loaded[action] = {
                    "name": shortcut.name,
                    "key": shortcut.key,
                    "group": shortcut.group,
                    "additionalKeywords": shortcut.additional_keywords,
                }
            shortcuts.update(loaded)
        except Exception as exc:
            LOGGER.warning(
                "Failed to load keyboard shortcuts from %r: %s",
                provider,
                exc,
            )

    return dict(sorted(shortcuts.items()))

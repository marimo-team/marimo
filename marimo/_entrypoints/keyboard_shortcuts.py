# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
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


def _load_keyboard_shortcuts(
    registry: EntryPointRegistry[object],
) -> KeyboardShortcuts:
    shortcuts: KeyboardShortcuts = {}

    for provider in registry.names():
        try:
            metadata = msgspec.convert(
                registry.get(provider),
                type=dict[object, object],
                strict=True,
            )
        except Exception as exc:
            LOGGER.warning(
                "Failed to load keyboard shortcuts from %r: %s",
                provider,
                exc,
            )
            continue

        for raw_shortcut_id, raw_shortcut in metadata.items():
            try:
                shortcut_id = msgspec.convert(
                    raw_shortcut_id,
                    type=str,
                    strict=True,
                )
                shortcut = msgspec.convert(
                    raw_shortcut,
                    type=_ShortcutMetadata,
                    strict=True,
                )
                if not shortcut_id.strip():
                    raise ValueError("shortcut IDs must not be empty")
                if not shortcut.name.strip():
                    raise ValueError("shortcut names must not be empty")
                if not shortcut.key.strip():
                    raise ValueError("shortcut keys must not be empty")
            except Exception as exc:
                LOGGER.warning(
                    "Failed to load keyboard shortcut %r from %r: %s",
                    raw_shortcut_id,
                    provider,
                    exc,
                )
                continue

            action = f"extension.{provider}.{shortcut_id}"
            shortcuts[action] = {
                "name": shortcut.name,
                "key": shortcut.key,
                "group": shortcut.group,
                "additionalKeywords": shortcut.additional_keywords,
            }

    return dict(sorted(shortcuts.items()))


@functools.lru_cache(maxsize=1)
def _load_installed_keyboard_shortcuts(
    registry: EntryPointRegistry[object],
) -> KeyboardShortcuts:
    return _load_keyboard_shortcuts(registry)


def load_keyboard_shortcuts(
    registry: EntryPointRegistry[object] | None = None,
) -> KeyboardShortcuts:
    """Load keyboard shortcut metadata from installed packages."""
    if registry is None:
        return {
            action: {
                "name": shortcut["name"],
                "key": shortcut["key"],
                "group": shortcut["group"],
                "additionalKeywords": shortcut["additionalKeywords"].copy(),
            }
            for action, shortcut in _load_installed_keyboard_shortcuts(
                _REGISTRY
            ).items()
        }

    return _load_keyboard_shortcuts(registry)

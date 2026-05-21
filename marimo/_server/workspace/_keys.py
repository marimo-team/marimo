# Copyright 2026 Marimo. All rights reserved.
"""Tagged-union ADT for notebook file keys.

The wire format is a string (HTTP query params, session `initialization_id`)
but inside the server we model the two cases explicitly:

- :class:`NewFileKey` — the untitled (`__new__`) notebook
- :class:`PathFileKey` — a notebook identified by a filesystem path
"""

from __future__ import annotations

from dataclasses import dataclass

# Wire-format sentinel for an untitled notebook. Preserved across HTTP query
# params and session initialization IDs.
NEW_FILE_WIRE: str = "__new__"


@dataclass(frozen=True)
class NewFileKey:
    """Sentinel key for an untitled notebook."""


@dataclass(frozen=True)
class PathFileKey:
    """Key for a notebook identified by a filesystem path.

    The `path` is the raw value supplied at the boundary; workspaces are
    responsible for normalizing and validating it.
    """

    path: str


FileKey = NewFileKey | PathFileKey


def parse_file_key(raw: str) -> FileKey:
    """Parse a wire-format string into a :class:`FileKey`.

    The literal `__new__` becomes a :class:`NewFileKey`; any other string is
    treated as a path. We match the sentinel exactly so non-sentinel keys
    flow through normal path validation rather than being short-circuited
    to the blank notebook.
    """
    if raw == NEW_FILE_WIRE:
        return NewFileKey()
    return PathFileKey(raw)


def serialize_file_key(key: FileKey) -> str:
    """Serialize a :class:`FileKey` back to its wire-format string."""
    if isinstance(key, NewFileKey):
        return NEW_FILE_WIRE
    return key.path

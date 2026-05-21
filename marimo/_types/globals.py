# Copyright 2026 Marimo. All rights reserved.
"""Type aliases for cell globals dicts.

`MutableGlobals` is the concrete `dict` passed through `exec` /
`eval`; `Globals` is the read-only view for consumers that only
inspect the dict (e.g. collecting a cell's defs after execution).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeAlias

Globals: TypeAlias = Mapping[str, Any]
MutableGlobals: TypeAlias = dict[str, Any]

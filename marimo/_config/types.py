# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

OnCellChangeType = Literal["lazy", "autorun"]
ExecutionType = Literal["relaxed", "strict"]
# TODO(akshayka): remove normal, migrate to compact
# normal == compact
WidthType = Literal["normal", "compact", "medium", "full", "columns"]
Theme = Literal["light", "dark", "system"]
ExportType = Literal["html", "markdown", "ipynb"]
SqlOutputType = Literal["polars", "lazy-polars", "pandas", "native", "auto"]
StoreKey = Literal["file", "redis", "rest", "tiered"]
CopilotMode = Literal["ask", "manual", "agent", "code_mode"]
CacheVerification = Literal["off", "on", "strict"]
# Built-in loader or installed marimo.cache.loader entry-point name.
CacheLoader = Literal["pickle", "json", "lazy"] | str

# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ExportAsHTMLRequest:
    download: bool
    files: List[str]
    include_code: bool
    asset_url: Optional[str] = None


@dataclass
class ExportAsScriptRequest:
    download: bool


@dataclass
class ExportAsMarkdownRequest:
    download: bool

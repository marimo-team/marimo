# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ExportAsHTMLRequest:
    download: bool
    files: list[str]
    include_code: bool
    asset_url: Optional[str] = None


@dataclass
class ExportAsScriptRequest:
    download: bool


@dataclass
class ExportAsIPYNBRequest:
    download: bool


@dataclass
class ExportAsMarkdownRequest:
    download: bool

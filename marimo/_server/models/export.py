# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

import msgspec


class ExportAsHTMLRequest(msgspec.Struct, rename="camel"):
    download: bool
    files: list[str]
    include_code: bool
    asset_url: Optional[str] = None


class ExportAsScriptRequest(msgspec.Struct, rename="camel"):
    download: bool


class ExportAsIPYNBRequest(msgspec.Struct, rename="camel"):
    download: bool


class ExportAsMarkdownRequest(msgspec.Struct, rename="camel"):
    download: bool

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from typing import Literal, TypedDict

if sys.version_info >= (3, 11):
    from typing import NotRequired
else:
    from typing_extensions import NotRequired

ISLANDS_JSON_SCRIPT_TYPE: str = "application/vnd.marimo.islands+json"
ISLANDS_JSON_SCHEMA_VERSION: Literal[1] = 1


class MarimoIslandCellPayload(TypedDict):
    cellId: str
    code: str
    outputHtml: str
    outputMimetype: str
    reactive: bool
    displayCode: bool
    displayOutput: bool


class MarimoIslandPayload(TypedDict):
    schemaVersion: Literal[1]
    appId: str
    dependencies: NotRequired[list[str]]
    cells: list[MarimoIslandCellPayload]

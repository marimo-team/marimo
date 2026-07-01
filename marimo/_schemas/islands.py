# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal, TypedDict

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
    cells: list[MarimoIslandCellPayload]

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.tools.cells import (
    GetCellOutputs,
    GetCellRuntimeData,
    GetLightweightCellMap,
)
from marimo._ai._tools.tools.datasource import GetDatabaseTables
from marimo._ai._tools.tools.errors import GetNotebookErrors
from marimo._ai._tools.tools.lint import LintNotebook
from marimo._ai._tools.tools.notebooks import GetActiveNotebooks
from marimo._ai._tools.tools.rules import GetMarimoRules
from marimo._ai._tools.tools.tables_and_variables import GetTablesAndVariables

SUPPORTED_BACKEND_AND_MCP_TOOLS: list[type[ToolBase[Any, Any]]] = [
    GetMarimoRules,
    GetActiveNotebooks,
    GetCellRuntimeData,
    GetCellOutputs,
    GetLightweightCellMap,
    GetTablesAndVariables,
    GetDatabaseTables,
    GetNotebookErrors,
    LintNotebook,
]

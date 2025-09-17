# Copyright 2025 Marimo. All rights reserved.
from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.tools.cells import (
    GetCellRuntimeData,
    GetLightweightCellMap,
)
from marimo._ai._tools.tools.notebooks import GetActiveNotebooks
from marimo._ai._tools.tools.tables_and_variables import GetTablesAndVariables

SUPPORTED_BACKEND_AND_MCP_TOOLS: list[type[ToolBase]] = [
    GetActiveNotebooks,
    GetCellRuntimeData,
    GetLightweightCellMap,
    GetTablesAndVariables,
]

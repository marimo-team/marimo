# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._plugins.ui._impl.tables.filter_context import FilterContext
from marimo._server.ai.table_filter import TableFilterAlias
from marimo._utils.msgspec_basestruct import BaseStruct


class AiTableFilterRequest(BaseStruct):
    request: str
    context: FilterContext


class AiTableFilterResponse(BaseStruct):
    fql: str | None
    explanation: str | None
    aliases: list[TableFilterAlias]

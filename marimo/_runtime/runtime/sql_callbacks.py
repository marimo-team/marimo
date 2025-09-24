# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union, cast

from marimo import _loggers
from marimo._messaging.ops import ValidateSQLResult
from marimo._runtime.requests import ValidateSQLRequest
from marimo._sql.engines.duckdb import INTERNAL_DUCKDB_ENGINE, DuckDBEngine
from marimo._sql.engines.types import EngineCatalog, QueryEngine
from marimo._tracer import kernel_tracer
from marimo._types.ids import VariableName

if TYPE_CHECKING:
    from marimo._runtime.runtime.kernel import Kernel


SQLConnectionType = Union[QueryEngine[Any], EngineCatalog[Any]]

LOGGER = _loggers.marimo_logger()


class SqlCallbacks:
    def __init__(self, kernel: Kernel):
        self._kernel = kernel

    @kernel_tracer.start_as_current_span("validate_sql_query")
    async def validate_sql(self, request: ValidateSQLRequest) -> None:
        """Validate an SQL query"""
        # TODO: Place request in queue
        variable_name = cast(VariableName, request.engine)
        engine: Optional[SQLConnectionType] = None
        if variable_name == INTERNAL_DUCKDB_ENGINE:
            engine = DuckDBEngine(connection=None)
            error = None
        else:
            engine, error = self._kernel.get_sql_connection(variable_name)

        if error is not None or engine is None:
            LOGGER.error("Failed to get engine %s", variable_name)
            ValidateSQLResult(
                request_id=request.request_id,
                result=None,
                error="Engine not found",
            ).broadcast()
            return

        if isinstance(engine, QueryEngine):
            result, error = engine.execute_in_explain_mode(request.query)  # type: ignore
        else:
            error = "Engine does not support explain mode"

        ValidateSQLResult(
            request_id=request.request_id,
            result=None,  # We aren't using the result yet
            error=error,
        ).broadcast()

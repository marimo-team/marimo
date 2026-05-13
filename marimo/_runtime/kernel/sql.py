# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from marimo import _loggers
from marimo._messaging.notification import ValidateSQLResultNotification
from marimo._messaging.notification_utils import broadcast_notification
from marimo._sql.engines.duckdb import INTERNAL_DUCKDB_ENGINE, DuckDBEngine
from marimo._sql.engines.types import QueryEngine
from marimo._sql.parse import SqlCatalogCheckResult, parse_sql
from marimo._tracer import kernel_tracer
from marimo._types.ids import VariableName

if TYPE_CHECKING:
    from marimo._runtime.commands import ValidateSQLCommand
    from marimo._runtime.runtime import Kernel
    from marimo._sql.engines.types import SQLConnectionType

LOGGER = _loggers.marimo_logger()


class SqlCallbacks:
    def __init__(self, kernel: Kernel):
        self._kernel = kernel

    async def _validate_sql_query(self, request: ValidateSQLCommand) -> None:
        """Validate an SQL query

        This will validate:
        - the syntax (parsing)
        - the catalog (table and column names)
        """
        request_id = request.request_id

        if request.only_parse:
            if request.dialect is None:
                broadcast_notification(
                    ValidateSQLResultNotification(
                        request_id=request_id,
                        error="Dialect is required when only parsing",
                    ),
                )
                return

            # Just parse the query (no DB connection required)
            parse_result, error = parse_sql(request.query, request.dialect)
            broadcast_notification(
                ValidateSQLResultNotification(
                    request_id=request_id,
                    parse_result=parse_result,
                    error=error,
                ),
            )
            return

        # Validate against the database
        # This can be cheap for in-memory engines (duckdb, sqlite)
        # But potentially expensive and requires an active connection for remote engines
        # For failed connections, we should not raise an error

        if request.engine is None:
            broadcast_notification(
                ValidateSQLResultNotification(
                    request_id=request_id,
                    error="Engine is required for validating catalog",
                ),
            )
            return

        variable_name = cast(VariableName, request.engine)
        engine: SQLConnectionType | None = None
        if variable_name == INTERNAL_DUCKDB_ENGINE:
            engine = DuckDBEngine(connection=None)
            error = None
        else:
            engine, error = self._kernel.get_sql_connection(variable_name)

        if error is not None or engine is None:
            broadcast_notification(
                ValidateSQLResultNotification(
                    request_id=request_id,
                    error="Failed to get engine " + variable_name,
                ),
            )
            return

        # Get the parse error for linting
        parse_result, parse_error = parse_sql(request.query, engine.dialect)
        if parse_error is not None:
            # We don't want to fail the validation if there is a parse error
            LOGGER.debug("Parse error: %s", parse_error)

        if not isinstance(engine, QueryEngine):
            broadcast_notification(
                ValidateSQLResultNotification(
                    request_id=request_id,
                    error=f"Engine {variable_name} does not support catalog validation.",
                    parse_result=parse_result,
                ),
            )
            return

        _, error_message = engine.execute_in_explain_mode(  # type: ignore
            request.query, self._kernel.globals
        )
        validate_result = SqlCatalogCheckResult(
            success=error_message is None,
            error_message=error_message,
        )
        broadcast_notification(
            ValidateSQLResultNotification(
                request_id=request_id,
                validate_result=validate_result,
                parse_result=parse_result,
                error=None,
            ),
        )

    @kernel_tracer.start_as_current_span("validate_sql")
    async def validate_sql(self, request: ValidateSQLCommand) -> None:
        """Validate an SQL query"""

        try:
            await self._validate_sql_query(request)
        except Exception as e:
            LOGGER.exception("Failed to validate SQL query")
            broadcast_notification(
                ValidateSQLResultNotification(
                    request_id=request.request_id,
                    error="Failed to validate SQL query: " + str(e),
                ),
            )

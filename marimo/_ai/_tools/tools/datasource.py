# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from marimo import _loggers
from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.types import SuccessResult
from marimo._ai._tools.utils.exceptions import ToolExecutionError
from marimo._data.models import DataTable
from marimo._server.sessions import Session
from marimo._types.ids import SessionId
from marimo._utils.fuzzy_match import compile_regex, is_fuzzy_match

LOGGER = _loggers.marimo_logger()


@dataclass
class GetDatabaseTablesArgs:
    session_id: SessionId
    query: Optional[str] = None


@dataclass
class TableDetails:
    connection: str
    database: str
    schema: str
    table: DataTable


@dataclass
class GetDatabaseTablesOutput(SuccessResult):
    tables: list[TableDetails] = field(default_factory=list)


class GetDatabaseTables(
    ToolBase[GetDatabaseTablesArgs, GetDatabaseTablesOutput]
):
    """
    Get information about tables in a database. Use the query parameter to search by name. Use regex for complex searches.

    Args:
        session_id: The session id.
        query (optional): The query to match the database, schemas, and tables.

    If a query is provided, it will fuzzy match the query to the database, schemas, and tables available. If no query is provided, all tables are returned. Don't provide a query if you need to see the entire schema view.

    The tables returned contain information about the database, schema and connection name to use in forming SQL queries.
    """

    def handle(self, args: GetDatabaseTablesArgs) -> GetDatabaseTablesOutput:
        session_id = args.session_id
        session = self.context.get_session(session_id)

        return self._get_tables(session, args.query)

    def _get_tables(
        self, session: Session, query: Optional[str]
    ) -> GetDatabaseTablesOutput:
        session_view = session.session_view
        data_connectors = session_view.data_connectors

        if len(data_connectors.connections) == 0:
            raise ToolExecutionError(
                message="No databases found. Please create a connection first.",
                code="NO_DATABASES_FOUND",
                is_retryable=False,
            )

        tables: list[TableDetails] = []

        # Pre-compile regex if query exists
        compiled_pattern = None
        is_regex = False
        if query:
            compiled_pattern, is_regex = compile_regex(query)

        for connection in data_connectors.connections:
            for database in connection.databases:
                for schema in database.schemas:
                    # If query is None, match all schemas
                    # If matching, add all tables to the list
                    if query is None or is_fuzzy_match(
                        query, schema.name, compiled_pattern, is_regex
                    ):
                        for table in schema.tables:
                            tables.append(
                                TableDetails(
                                    connection=connection.name,
                                    database=database.name,
                                    schema=schema.name,
                                    table=table,
                                )
                            )
                        continue
                    for table in schema.tables:
                        if is_fuzzy_match(
                            query, table.name, compiled_pattern, is_regex
                        ):
                            tables.append(
                                TableDetails(
                                    connection=connection.name,
                                    database=database.name,
                                    schema=schema.name,
                                    table=table,
                                )
                            )

        return GetDatabaseTablesOutput(
            tables=tables,
            next_steps=[
                'Example of an SQL query: _df = mo.sql(f"""SELECT * FROM database.schema.name LIMIT 100""")',
            ],
        )

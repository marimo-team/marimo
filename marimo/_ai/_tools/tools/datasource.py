# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from marimo import _loggers
from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.types import SuccessResult, ToolGuidelines
from marimo._ai._tools.utils.exceptions import ToolExecutionError
from marimo._data.models import DataTable
from marimo._sql.engines.duckdb import INTERNAL_DUCKDB_ENGINE
from marimo._types.ids import SessionId
from marimo._utils.fuzzy_match import compile_regex, is_fuzzy_match

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from marimo._session import Session


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
    sample_query: str


@dataclass
class GetDatabaseTablesOutput(SuccessResult):
    tables: list[TableDetails] = field(default_factory=list)


class GetDatabaseTables(
    ToolBase[GetDatabaseTablesArgs, GetDatabaseTablesOutput]
):
    """
    Get information about tables in a database. Use the query parameter to search by name. You can use regex.

    Args:
        session_id: The session id.
        query (optional): The query to match the database, schemas, and tables.

    If a query is provided, it will fuzzy match the query to the database, schemas, and tables available. If no query is provided, all tables are returned.
    """

    guidelines = ToolGuidelines(
        when_to_use=[
            "When exploring database tables from external connections (SQL databases)",
            "Before writing SQL queries to understand schema structure",
        ],
        prerequisites=[
            "You must have a valid session id from an active notebook",
        ],
        avoid_if=[
            "You have already been given the schema view, you can refer to the given information",
            "The user is asking about in-memory DataFrames, use the get_tables_and_variables tool instead",
        ],
        additional_info="For best results, don't provide a query since you may miss some tables. Alternatively, provide loose queries using regex that can match uppercase/lowercase and plural or singular forms.",
    )

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
                default_database = connection.default_database == database.name
                for schema in database.schemas:
                    default_schema = connection.default_schema == schema.name
                    # If query is None, match all schemas
                    # If matching, add all tables to the list
                    if query is None or is_fuzzy_match(
                        query, schema.name, compiled_pattern, is_regex
                    ):
                        for table in schema.tables:
                            sample_query = self._form_sample_query(
                                database=database.name,
                                schema=schema.name,
                                table=table.name,
                                default_database=default_database,
                                default_schema=default_schema,
                                engine=connection.name,
                            )
                            tables.append(
                                TableDetails(
                                    connection=connection.name,
                                    database=database.name,
                                    schema=schema.name,
                                    table=table,
                                    sample_query=sample_query,
                                )
                            )
                        continue
                    for table in schema.tables:
                        if is_fuzzy_match(
                            query, table.name, compiled_pattern, is_regex
                        ):
                            sample_query = self._form_sample_query(
                                database=database.name,
                                schema=schema.name,
                                table=table.name,
                                default_database=default_database,
                                default_schema=default_schema,
                                engine=connection.name,
                            )
                            tables.append(
                                TableDetails(
                                    connection=connection.name,
                                    database=database.name,
                                    schema=schema.name,
                                    table=table,
                                    sample_query=sample_query,
                                )
                            )

        return GetDatabaseTablesOutput(
            tables=tables,
            next_steps=[
                "Use the sample query as a guideline to write your own SQL query."
            ],
        )

    def _form_sample_query(
        self,
        *,
        database: str,
        schema: str,
        table: str,
        default_database: bool,
        default_schema: bool,
        engine: str,
    ) -> str:
        sample_query = f"SELECT * FROM {database}.{schema}.{table} LIMIT 100"
        if default_database:
            sample_query = f"SELECT * FROM {schema}.{table} LIMIT 100"
        if default_schema:
            sample_query = f"SELECT * FROM {table} LIMIT 100"
        if engine != INTERNAL_DUCKDB_ENGINE:
            wrapped_query = (
                f'df = mo.sql(f"""{sample_query}""", engine={engine})'
            )
        else:
            wrapped_query = f'df = mo.sql(f"""{sample_query}""")'
        return wrapped_query

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.types import SuccessResult, ToolGuidelines
from marimo._data.models import DataTableColumn
from marimo._messaging.notification import VariableValue
from marimo._session import Session
from marimo._types.ids import SessionId


@dataclass
class TablesAndVariablesArgs:
    session_id: SessionId
    variable_names: list[str]


@dataclass
class DataTableMetadata:
    """
    Metadata about a data table.

    source: str - Can be dialect, or source db name.
    engine: str - The engine or connection handler of the data table.
    num_rows: int - The number of rows in the data table.
    num_columns: int - The number of columns in the data table.
    columns: list[DataTableColumn] - The columns in the data table.
    primary_keys: Optional[list[str]] - The primary keys of the data table.
    indexes: Optional[list[str]] - The indexes of the data table.
    """

    source: str
    num_rows: Optional[int]
    num_columns: Optional[int]
    columns: list[DataTableColumn]
    engine: Optional[str]
    primary_keys: Optional[list[str]]
    indexes: Optional[list[str]]


@dataclass
class TablesAndVariablesOutput(SuccessResult):
    tables: dict[str, DataTableMetadata] = field(default_factory=dict)
    variables: dict[str, VariableValue] = field(default_factory=dict)


class GetTablesAndVariables(
    ToolBase[TablesAndVariablesArgs, TablesAndVariablesOutput]
):
    """
    Get tables and variables information in the session.

    When provided with a list of variable names, it will return information about the variables and tables mentioned.
    If an empty list is provided, it will return information about all tables and variables.

    Returns:
        A success result containing tables (columns, primary keys, indexes, engine, etc.) and variables (value, data type).
    """

    guidelines = ToolGuidelines(
        when_to_use=[
            "When inspecting in-memory DataFrames or Python variables in the notebook",
            "Before suggesting data operations to understand available data",
        ],
        prerequisites=[
            "You must have a valid session id from an active notebook",
        ],
        avoid_if=[
            "the user is asking about database tables or data sources, use the get_database_tables tool instead",
        ],
    )

    def handle(self, args: TablesAndVariablesArgs) -> TablesAndVariablesOutput:
        session = self.context.get_session(args.session_id)
        return self._get_tables_and_variables(session, args.variable_names)

    def _get_tables_and_variables(
        self, session: Session, variable_names: list[str]
    ) -> TablesAndVariablesOutput:
        session_view = session.session_view
        # convert to set for O(1) lookup
        variable_names_set = set(variable_names)
        return_all_vars = variable_names_set == set()

        tables = session_view.datasets.tables
        variables = session_view.variable_values

        filtered_tables = (
            tables
            if return_all_vars
            else filter(lambda table: table.name in variable_names_set, tables)
        )
        filtered_variables = (
            variables
            if return_all_vars
            else filter(
                lambda variable: variable in variable_names_set, variables
            )
        )

        data_tables: dict[str, DataTableMetadata] = {}
        for table in filtered_tables:
            data_tables[table.name] = DataTableMetadata(
                source=table.source,
                num_rows=table.num_rows,
                num_columns=table.num_columns,
                columns=table.columns,
                primary_keys=table.primary_keys,
                indexes=table.indexes,
                engine=table.engine,
            )

        notebook_variables: dict[str, VariableValue] = {}
        for variable_name in filtered_variables:
            value = variables[variable_name]
            notebook_variables[variable_name] = VariableValue(
                name=variable_name,
                value=value.value,
                datatype=value.datatype,
            )

        return TablesAndVariablesOutput(
            tables=data_tables, variables=notebook_variables
        )

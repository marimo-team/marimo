# Copyright 2025 Marimo. All rights reserved.
from dataclasses import dataclass, field
from typing import Any, Optional

from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.tools.cells import CellVariableValue
from marimo._ai._tools.types import SuccessResult
from marimo._server.sessions import Session
from marimo._types.ids import SessionId


@dataclass
class TablesAndVariablesArgs:
    session_id: SessionId
    variable_names: list[str]


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    external_type: str
    sample_values: list[Any]


@dataclass
class DataTableMetadata:
    source: str
    num_rows: int
    num_columns: int
    columns: list[ColumnInfo]
    primary_keys: Optional[list[str]]
    indexes: Optional[list[str]]


@dataclass
class TablesAndVariablesOutput(SuccessResult):
    tables: dict[str, DataTableMetadata] = field(default_factory=dict)
    variables: dict[str, CellVariableValue] = field(default_factory=dict)


class GetTablesAndVariables(
    ToolBase[TablesAndVariablesArgs, TablesAndVariablesOutput]
):
    """
    Get tables and variables information in the session.

    When provided with a list of variable names, it will return information about the variables and tables mentioned.
    If an empty list is provided, it will return information about all tables and variables.

    Returns:
        A success result containing tables (columns, primary keys, indexes, etc.) and variables (value, data type).
    """

    def handle(self, args: TablesAndVariablesArgs) -> TablesAndVariablesOutput:
        session_manager = self.context.session_manager
        session = session_manager.get_session(args.session_id)

        return self._get_tables_and_variables(session, args.variable_names)

    def _get_tables_and_variables(
        self, session: "Session", variable_names: list[str]
    ) -> TablesAndVariablesOutput:
        session_view = session.session_view
        return_all_vars = variable_names == []

        tables = session_view.datasets.tables
        variables = session_view.variable_values

        filtered_tables = filter(
            lambda table: table.name in variable_names or return_all_vars,
            tables,
        )

        filtered_variables = filter(
            lambda variable: variable in variable_names or return_all_vars,
            variables,
        )

        data_tables: dict[str, DataTableMetadata] = {}
        for table in filtered_tables:
            data_tables[table.name] = DataTableMetadata(
                source=table.source_type,
                num_rows=table.num_rows,
                num_columns=table.num_columns,
                columns=table.columns,
                primary_keys=table.primary_keys,
                indexes=table.indexes,
            )

        notebook_variables: dict[str, CellVariableValue] = {}
        for variable_name in filtered_variables:
            value = variables[variable_name]
            notebook_variables[variable_name] = CellVariableValue(
                name=variable_name,
                value=value.value,
                data_type=value.datatype,
            )

        return TablesAndVariablesOutput(
            tables=data_tables, variables=notebook_variables
        )

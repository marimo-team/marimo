# Copyright 2025 Marimo. All rights reserved.
# This tool is ready, but needs session to be passed in

# from __future__ import annotations

# from typing import Any, Optional, TypedDict

# from marimo import _loggers
# from marimo._data.models import DataType, ExternalDataType
# from marimo._server.ai.tools.types import BackendTool, Tool
# from marimo._server.sessions import Session

# LOGGER = _loggers.marimo_logger()


# class DataTableMetadataArgs(TypedDict):
#     variable_names: list[str]


# class ColumnInfo(TypedDict):
#     name: str
#     data_type: DataType
#     external_type: ExternalDataType
#     sample_values: list[Any]


# class DataTableMetadata(TypedDict):
#     source: str
#     num_rows: int
#     num_columns: int
#     columns: list[ColumnInfo]
#     primary_keys: Optional[list[str]]
#     indexes: Optional[list[str]]


# class DataTableMetadataResponse(TypedDict):
#     success: bool
#     error: Optional[str]
#     data_tables: dict[str, DataTableMetadata]


# class GetDataTablesMetadataTool(BackendTool[DataTableMetadataArgs]):
#     """A tool that gets metadata about DataTable variables."""

#     @property
#     def tool(self) -> Tool:
#         return Tool(
#             name="get_data_tables_metadata_tool",
#             description="A tool that gets metadata about data tables, this includes dataframes and sql tables.",
#             parameters={
#                 "type": "object",
#                 "properties": {
#                     "variable_names": {
#                         "type": "array",
#                         "items": {
#                             "type": "string",
#                         },
#                         "description": "The data table variable names to get metadata for",
#                     },
#                 },
#                 "required": ["variable_names"],
#             },
#             source="backend",
#             mode=["ask"],
#         )

#     def handler(
#         self, arguments: DataTableMetadataArgs, session: Session
#     ) -> DataTableMetadataResponse:
#         """
#         Handle the sample tool execution.

#         Args:
#             arguments: The validated arguments passed to the tool
#             session: The session of the notebook

#         Returns:
#             Dictionary containing the tool's response
#         """
#         try:
#             # Extract parameters with defaults
#             variable_names = arguments.get("variable_names", [])
#             if not variable_names:
#                 response = DataTableMetadataResponse(
#                     success=True,
#                     error="No variable names provided",
#                     data_tables={},
#                 )
#                 return response

#             # Get the DataTable
#             session_view = session.session_view
#             datasets = session_view.datasets
#             if not datasets.tables:
#                 return DataTableMetadataResponse(
#                     success=True,
#                     error="No datasets found",
#                     data_tables={},
#                 )

#             data_tables: dict[str, DataTableMetadata] = {}
#             for table in datasets.tables:
#                 table_var_name = table.variable_name or table.name
#                 if table_var_name in variable_names:
#                     data_tables[table_var_name] = {
#                         "source": table.source,
#                         "num_rows": table.num_rows,
#                         "num_columns": table.num_columns,
#                         "columns": [
#                             ColumnInfo(
#                                 name=column.name,
#                                 data_type=column.type,
#                                 external_type=column.external_type,
#                                 sample_values=column.sample_values,
#                             )
#                             for column in table.columns
#                         ],
#                         "primary_keys": table.primary_keys,
#                         "indexes": table.indexes,
#                     }

#             return DataTableMetadataResponse(
#                 success=True,
#                 error=None,
#                 data_tables=data_tables,
#             )

#         except Exception as e:
#             # Handle errors gracefully
#             LOGGER.error(f"Error in sample tool: {str(e)}")
#             return DataTableMetadataResponse(
#                 success=False,
#                 error=f"Tool execution failed: {str(e)}",
#                 data_tables={},
#             )

#     def validator(
#         self, arguments: DataTableMetadataArgs
#     ) -> Optional[tuple[bool, str]]:
#         """
#         Validate parameters for the sample tool.

#         This function is optional but recommended for robust parameter validation.

#         Args:
#             arguments: The arguments to validate

#         Returns:
#             Tuple of (is_valid, error_message). If is_valid is True, error_message is empty.
#         """
#         del arguments
#         return None

# Copyright 2025 Marimo. All rights reserved.

import json
from typing import Optional

from marimo._sql.engines.duckdb import DuckDBEngine

SUPPORTED_DIALECTS = ["duckdb"]

# skip to reduce the response size
# the response doesn't matter too much, we are interested in the errors
JSON_SERIALIZE_QUERY = "SELECT JSON_SERIALIZE_SQL(?, skip_null := true, skip_empty := true, skip_default := true)"


class ParserError(Exception):
    def __init__(
        self,
        error_message: str,
        position: Optional[int],
        error_subtype: Optional[str],
    ):
        super().__init__(error_message)
        self.error_subtype = error_subtype
        self.position = position


def extract_error_response(
    data: dict,
) -> Optional[ParserError]:
    has_error = data.get("error")
    error_type = data.get("error_type")
    error_message = data.get("error_message")
    position = data.get("position")
    error_subtype = data.get("SYNTAX_ERROR")

    if has_error and error_type == "parser":
        return ParserError(
            error_message=error_message or "Syntax error in query",
            position=position,
            error_subtype=error_subtype,
        )

    if has_error and error_type == "not implemented":
        # likely a valid query, but only SELECT statements are supported
        return None

    return None


def parse_sql(query: str, dialect: str) -> Optional[ParserError]:
    """Parses an SQL query. Returns syntax errors. Does not check for catalog errors. Currently only supports DuckDB.

    Args:
        query (str): The SQL query to parse.
        dialect (str): The dialect of the SQL query.

    Returns:
        str: The syntax errors in the SQL query.
    """
    if dialect.strip().lower() not in SUPPORTED_DIALECTS:
        raise NotImplementedError(f"Dialect {dialect} not supported")

    relation = DuckDBEngine.execute_and_return_relation(
        JSON_SERIALIZE_QUERY, params=[query]
    )
    result = relation.fetchall()
    json_response = result[0][0]
    parsed_json = json.loads(json_response)
    return extract_error_response(parsed_json)

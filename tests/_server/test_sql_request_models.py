# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec

from marimo._server.models.models import (
    ListSQLSchemasRequest,
    ListSQLTablesRequest,
    PreviewSQLTableRequest,
)


def test_list_sql_schemas_request_preserves_schema_path() -> None:
    # Wire format is camelCase (Command uses rename="camel").
    body = (
        b'{"requestId":"1","engine":"e","database":"top",'
        b'"schemaPath":["nested"]}'
    )
    request = msgspec.json.decode(body, type=ListSQLSchemasRequest)
    assert request.schema_path == ["nested"]
    # as_command must not drop the field.
    assert request.as_command().schema_path == ["nested"]


def test_list_sql_tables_request_preserves_schema_path() -> None:
    body = (
        b'{"requestId":"1","engine":"e","database":"top","schema":"deep",'
        b'"schemaPath":["nested","deep"]}'
    )
    request = msgspec.json.decode(body, type=ListSQLTablesRequest)
    assert request.schema_path == ["nested", "deep"]
    assert request.as_command().schema_path == ["nested", "deep"]


def test_preview_sql_table_request_preserves_schema_path() -> None:
    body = (
        b'{"requestId":"1","engine":"e","database":"top","schema":"deep",'
        b'"tableName":"t","schemaPath":["nested","deep"]}'
    )
    request = msgspec.json.decode(body, type=PreviewSQLTableRequest)
    assert request.schema_path == ["nested", "deep"]
    assert request.as_command().schema_path == ["nested", "deep"]


def test_schema_path_defaults_to_empty() -> None:
    # Older clients omit the field entirely.
    body = b'{"requestId":"1","engine":"e","database":"top","schema":"s","tableName":"t"}'
    request = msgspec.json.decode(body, type=PreviewSQLTableRequest)
    assert request.schema_path == []
    assert request.as_command().schema_path == []

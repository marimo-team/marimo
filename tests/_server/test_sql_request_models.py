# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec

from marimo._server.models.models import (
    ListCatalogChildrenRequest,
    PreviewSQLTableRequest,
)


def test_list_catalog_children_request_preserves_catalog_path() -> None:
    body = (
        b'{"requestId":"1","engine":"e","database":"top",'
        b'"catalogPath":["nested","deep"]}'
    )
    request = msgspec.json.decode(body, type=ListCatalogChildrenRequest)
    assert request.catalog_path == ["nested", "deep"]
    assert request.as_command().catalog_path == ["nested", "deep"]


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

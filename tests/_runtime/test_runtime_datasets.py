# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.ops import (
    DataSourceConnections,
    SQLMetadata,
    SQLTableListPreview,
    SQLTablePreview,
    ValidateSQLResult,
)
from marimo._runtime.requests import (
    ExecutionRequest,
    PreviewDataSourceConnectionRequest,
    PreviewSQLTableListRequest,
    PreviewSQLTableRequest,
    ValidateSQLRequest,
)
from marimo._sql.engines.duckdb import INTERNAL_DUCKDB_ENGINE
from marimo._sql.parse import SqlCatalogCheckResult, SqlParseResult
from marimo._types.ids import CellId_t, RequestId
from tests.conftest import MockedKernel

HAS_SQL = DependencyManager.duckdb.has() and DependencyManager.polars.has()


DUCKDB_CONN = "duckdb_conn"
SQLITE_CONN = "sqlite_conn"


@pytest.fixture
async def connection_requests() -> list[ExecutionRequest]:
    return [
        ExecutionRequest(cell_id=CellId_t("0"), code="import duckdb"),
        ExecutionRequest(
            cell_id=CellId_t("1"),
            code=f"{DUCKDB_CONN} = duckdb.connect(':memory:')",
        ),
        ExecutionRequest(cell_id=CellId_t("2"), code="import sqlite3"),
        ExecutionRequest(
            cell_id=CellId_t("3"),
            code=f"{SQLITE_CONN} = sqlite3.connect(':memory:')",
        ),
    ]


# @pytest.mark.skipif(not HAS_SQL, reason="SQL deps not available")
# class TestGetSQLConnection:
#     async def test_non_existent_engine(
#         self, mocked_kernel: MockedKernel
#     ) -> None:
#         k = mocked_kernel.k

#         # Non-existent engine
#         k.get_sql_connection(DUCKDB_CONN)
#         assert k.get_sql_connection(DUCKDB_CONN) == (None, "Engine not found")

#     async def test_created_engine(
#         self,
#         mocked_kernel: MockedKernel,
#         connection_requests: list[ExecutionRequest],
#     ) -> None:
#         k = mocked_kernel.k

#         # Create duckdb and sqlite connections
#         await k.run(connection_requests)

#         connection, error = k.get_sql_connection("duckdb_conn")
#         assert connection is not None
#         assert error is None

#         # Test with SQLite engine (which is a QueryEngine, but not a EngineCatalog)
#         connection, error = k.get_sql_connection(SQLITE_CONN)
#         assert connection is not None
#         assert error is None


@pytest.mark.skipif(not HAS_SQL, reason="SQL deps not available")
class TestPreviewSQLTable:
    async def test_non_existent_engine(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        preview_sql_table_request = PreviewSQLTableRequest(
            request_id=RequestId("0"),
            engine=DUCKDB_CONN,
            database="test",
            schema="test",
            table_name="t1",
        )
        await k.handle_message(preview_sql_table_request)

        preview_sql_table_results = [
            op for op in stream.operations if isinstance(op, SQLTablePreview)
        ]
        assert preview_sql_table_results == [
            SQLTablePreview(
                request_id=RequestId("0"),
                table=None,
                error="Engine not found",
                metadata=SQLMetadata(
                    connection=DUCKDB_CONN, database="test", schema="test"
                ),
            )
        ]

    async def test_catalog_engine(
        self,
        mocked_kernel: MockedKernel,
        connection_requests: list[ExecutionRequest],
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(connection_requests)

        preview_sql_table_request = PreviewSQLTableRequest(
            request_id=RequestId("0"),
            engine=DUCKDB_CONN,
            database="test",
            schema="test",
            table_name="t1",
        )
        await k.handle_message(preview_sql_table_request)

        preview_sql_table_results = [
            op for op in stream.operations if isinstance(op, SQLTablePreview)
        ]
        assert preview_sql_table_results == [
            SQLTablePreview(
                request_id=RequestId("0"),
                table=None,
                error=None,
                metadata=SQLMetadata(
                    connection=DUCKDB_CONN, database="test", schema="test"
                ),
            )
        ]

    async def test_query_engine(
        self,
        mocked_kernel: MockedKernel,
        connection_requests: list[ExecutionRequest],
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(connection_requests)

        preview_sql_table_request = PreviewSQLTableRequest(
            request_id=RequestId("0"),
            engine=SQLITE_CONN,
            database="test",
            schema="test",
            table_name="t1",
        )
        await k.handle_message(preview_sql_table_request)

        preview_sql_table_results = [
            op for op in stream.operations if isinstance(op, SQLTablePreview)
        ]
        assert preview_sql_table_results == [
            SQLTablePreview(
                request_id=RequestId("0"),
                table=None,
                error="Connection does not support catalog operations",
                metadata=SQLMetadata(
                    connection=SQLITE_CONN, database="test", schema="test"
                ),
            )
        ]


@pytest.mark.skipif(not HAS_SQL, reason="SQL deps not available")
class TestPreviewSQLTableList:
    async def test_non_existent_engine(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        preview_sql_table_list_request = PreviewSQLTableListRequest(
            request_id=RequestId("0"),
            engine=DUCKDB_CONN,
            database="test",
            schema="test",
        )
        await k.handle_message(preview_sql_table_list_request)
        preview_sql_table_list_results = [
            op
            for op in stream.operations
            if isinstance(op, SQLTableListPreview)
        ]
        assert preview_sql_table_list_results == [
            SQLTableListPreview(
                request_id=RequestId("0"),
                tables=[],
                error="Engine not found",
                metadata=SQLMetadata(
                    connection=DUCKDB_CONN, database="test", schema="test"
                ),
            )
        ]

    async def test_catalog_engine(
        self,
        mocked_kernel: MockedKernel,
        connection_requests: list[ExecutionRequest],
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(connection_requests)

        preview_sql_table_list_request = PreviewSQLTableListRequest(
            request_id=RequestId("0"),
            engine=DUCKDB_CONN,
            database="test",
            schema="test",
        )
        await k.handle_message(preview_sql_table_list_request)

        preview_sql_table_list_results = [
            op
            for op in stream.operations
            if isinstance(op, SQLTableListPreview)
        ]
        assert preview_sql_table_list_results == [
            SQLTableListPreview(
                request_id=RequestId("0"),
                tables=[],
                error=None,
                metadata=SQLMetadata(
                    connection=DUCKDB_CONN, database="test", schema="test"
                ),
            )
        ]

    async def test_query_engine(
        self,
        mocked_kernel: MockedKernel,
        connection_requests: list[ExecutionRequest],
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(connection_requests)

        preview_sql_table_list_request = PreviewSQLTableListRequest(
            request_id=RequestId("0"),
            engine=SQLITE_CONN,
            database="test",
            schema="test",
        )
        await k.handle_message(preview_sql_table_list_request)

        preview_sql_table_list_results = [
            op
            for op in stream.operations
            if isinstance(op, SQLTableListPreview)
        ]
        assert preview_sql_table_list_results == [
            SQLTableListPreview(
                request_id=RequestId("0"),
                tables=[],
                error="Connection does not support catalog operations",
                metadata=SQLMetadata(
                    connection=SQLITE_CONN, database="test", schema="test"
                ),
            )
        ]


class TestPreviewDatasourceConnection:
    async def test_non_existent_engine(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        preview_datasource_connection_request = (
            PreviewDataSourceConnectionRequest(engine=DUCKDB_CONN)
        )
        await k.handle_message(preview_datasource_connection_request)
        preview_datasource_connection_results = [
            op
            for op in stream.operations
            if isinstance(op, DataSourceConnections)
        ]
        assert preview_datasource_connection_results == []

    @pytest.mark.xfail(
        reason="Should have only 2 connections (duckdb and sqlite)"
    )
    async def test_engines(
        self,
        mocked_kernel: MockedKernel,
        connection_requests: list[ExecutionRequest],
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(connection_requests)

        preview_datasource_connection_request = (
            PreviewDataSourceConnectionRequest(engine=DUCKDB_CONN)
        )
        await k.handle_message(preview_datasource_connection_request)

        preview_datasource_connection_results = [
            op
            for op in stream.operations
            if isinstance(op, DataSourceConnections)
        ]
        assert len(preview_datasource_connection_results) == 2


@pytest.mark.skipif(not HAS_SQL, reason="SQL deps not available")
class TestSQLValidate:
    async def test_non_existent_engine(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        # Non-existent engine
        validate_sql_request = ValidateSQLRequest(
            request_id=RequestId("0"),
            engine=DUCKDB_CONN,
            query="SELECT * from t1",
            only_parse=False,
        )
        await k.handle_message(validate_sql_request)
        validate_sql_results = [
            op for op in stream.operations if isinstance(op, ValidateSQLResult)
        ]
        assert validate_sql_results == [
            ValidateSQLResult(
                request_id=RequestId("0"),
                parse_result=None,
                validate_result=None,
                error="Failed to get engine duckdb_conn",
            )
        ]

    async def test_internal_engine_and_valid_query(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        # Internal engine and valid query
        validate_sql_request = ValidateSQLRequest(
            request_id=RequestId("1"),
            engine=INTERNAL_DUCKDB_ENGINE,
            query="SELECT 1, 2",
            only_parse=False,
        )
        await k.handle_message(validate_sql_request)
        validate_sql_results = [
            op for op in stream.operations if isinstance(op, ValidateSQLResult)
        ]
        assert validate_sql_results[-1] == ValidateSQLResult(
            request_id=RequestId("1"),
            parse_result=SqlParseResult(success=True, errors=[]),
            validate_result=SqlCatalogCheckResult(
                success=True, error_message=None
            ),
            error=None,
        )

    async def test_internal_engine_and_invalid_query(
        self, mocked_kernel: MockedKernel
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        # Internal engine and invalid query
        validate_sql_request = ValidateSQLRequest(
            request_id=RequestId("2"),
            engine=INTERNAL_DUCKDB_ENGINE,
            query="SELECT * FROM t1",
            only_parse=False,
        )
        await k.handle_message(validate_sql_request)
        validate_sql_results = [
            op for op in stream.operations if isinstance(op, ValidateSQLResult)
        ]
        latest_validate_sql_result = validate_sql_results[-1]
        assert latest_validate_sql_result.request_id == RequestId("2")

        assert latest_validate_sql_result.parse_result is not None
        # query is syntactically valid
        assert latest_validate_sql_result.parse_result.success is True
        assert len(latest_validate_sql_result.parse_result.errors) == 0

        assert latest_validate_sql_result.validate_result is not None
        assert latest_validate_sql_result.validate_result.success is False
        assert (
            latest_validate_sql_result.validate_result.error_message
            is not None
        )
        assert latest_validate_sql_result.error is None

        stream.operations.clear()

    async def test_other_engine_and_valid_query(
        self,
        mocked_kernel: MockedKernel,
        connection_requests: list[ExecutionRequest],
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        # Handle other engines
        await k.run(connection_requests)
        validate_sql_request = ValidateSQLRequest(
            request_id=RequestId("3"),
            engine=SQLITE_CONN,
            query="SELECT 1, 2",
            only_parse=False,
        )
        await k.handle_message(validate_sql_request)
        validate_sql_results = [
            op for op in stream.operations if isinstance(op, ValidateSQLResult)
        ]
        assert (
            validate_sql_results[-1]
            == ValidateSQLResult(
                request_id=RequestId("3"),
                parse_result=None,  # Currently does not support parse errors for non-duckdb engines
                validate_result=SqlCatalogCheckResult(
                    success=True, error_message=None
                ),
                error=None,
            )
        )

    async def test_only_parse_with_no_dialect(
        self,
        mocked_kernel: MockedKernel,
        connection_requests: list[ExecutionRequest],
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(connection_requests)

        validate_sql_request = ValidateSQLRequest(
            request_id=RequestId("4"),
            engine=SQLITE_CONN,
            query="SELECT 1, 2",
            only_parse=True,
        )
        await k.handle_message(validate_sql_request)

        validate_sql_results = [
            op for op in stream.operations if isinstance(op, ValidateSQLResult)
        ]
        assert validate_sql_results[-1] == ValidateSQLResult(
            request_id=RequestId("4"),
            parse_result=None,
            validate_result=None,
            error="Dialect is required when only parsing",
        )

    async def test_only_parse_unsupported_dialect(
        self,
        mocked_kernel: MockedKernel,
        connection_requests: list[ExecutionRequest],
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(connection_requests)

        validate_sql_request = ValidateSQLRequest(
            request_id=RequestId("5"),
            dialect="sqlite",
            query="SELECT 1, 2",
            only_parse=True,
        )
        await k.handle_message(validate_sql_request)

        validate_sql_results = [
            op for op in stream.operations if isinstance(op, ValidateSQLResult)
        ]
        assert validate_sql_results[-1] == ValidateSQLResult(
            request_id=RequestId("5"),
            parse_result=None,
            validate_result=None,
            error="Unsupported dialect: sqlite",
        )

    async def test_only_parse_duckdb(
        self,
        mocked_kernel: MockedKernel,
        connection_requests: list[ExecutionRequest],
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(connection_requests)

        validate_sql_request = ValidateSQLRequest(
            request_id=RequestId("6"),
            dialect="duckdb",
            query="SELECT 1, 2",
            only_parse=True,
        )
        await k.handle_message(validate_sql_request)

        validate_sql_results = [
            op for op in stream.operations if isinstance(op, ValidateSQLResult)
        ]
        assert validate_sql_results[-1] == ValidateSQLResult(
            request_id=RequestId("6"),
            parse_result=SqlParseResult(success=True, errors=[]),
            validate_result=None,
            error=None,
        )

    async def test_validate_but_no_engine(
        self,
        mocked_kernel: MockedKernel,
        connection_requests: list[ExecutionRequest],
    ) -> None:
        k = mocked_kernel.k
        stream = mocked_kernel.stream

        await k.run(connection_requests)

        validate_sql_request = ValidateSQLRequest(
            request_id=RequestId("7"),
            query="SELECT 1, 2",
            only_parse=False,
        )
        await k.handle_message(validate_sql_request)

        validate_sql_results = [
            op for op in stream.operations if isinstance(op, ValidateSQLResult)
        ]
        assert validate_sql_results[-1] == ValidateSQLResult(
            request_id=RequestId("7"),
            parse_result=None,
            validate_result=None,
            error="Engine is required for validating catalog",
        )

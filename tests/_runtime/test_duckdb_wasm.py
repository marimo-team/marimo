# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import gzip
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._runtime._wasm._duckdb import (
    patch_duckdb_for_wasm,
    patch_duckdb_query_for_wasm,
)
from marimo._runtime._wasm._duckdb.sources import (
    remote_file_source_from_table,
)
from marimo._sql.engines.duckdb import DuckDBEngine
from tests.conftest import ExecReqProvider, mock_pyodide

pytestmark = pytest.mark.requires("duckdb", "pandas", "sqlglot")

pytest.importorskip("duckdb")
pytest.importorskip("pandas")
pytest.importorskip("sqlglot")

if TYPE_CHECKING:
    from collections.abc import Sequence

    from marimo._runtime.runtime import Kernel


def _normalize_value(value: object) -> object:
    import pandas as pd

    if hasattr(value, "tolist") and not isinstance(
        value, dict | list | str | bytes | bytearray
    ):
        return value.tolist()
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_value(item) for key, item in value.items()}
    if isinstance(value, bytes | bytearray):
        return bytes(value)
    try:
        return None if bool(pd.isna(value)) else value
    except (TypeError, ValueError):
        return value


def _records(df: object) -> list[dict[str, object]]:
    return [
        {key: _normalize_value(value) for key, value in row.items()}
        for row in df.to_dict("records")  # type: ignore[attr-defined]
    ]


def _rows(rows: Sequence[Sequence[object]]) -> list[tuple[object, ...]]:
    return [tuple(_normalize_value(value) for value in row) for row in rows]


@dataclass(frozen=True)
class RemoteFixture:
    url: str
    suffix: str
    data: bytes


@dataclass(frozen=True)
class QueryParityCase:
    name: str
    query: str
    fixtures: tuple[RemoteFixture, ...]


@dataclass(frozen=True)
class DirectReadParityCase:
    name: str
    function_name: str
    fixture: RemoteFixture
    source_kwarg: str | None = None
    options: tuple[tuple[str, object], ...] = ()


def _parquet_bytes(sql: str) -> bytes:
    import duckdb

    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as file:
        path = Path(file.name)
    try:
        duckdb.sql(sql).write_parquet(str(path))
        return path.read_bytes()
    finally:
        path.unlink(missing_ok=True)


def _local_fixture_path(
    fixture: RemoteFixture, tmp_path: Path, filename: str
) -> str:
    path = tmp_path / f"{filename}{fixture.suffix}"
    path.write_bytes(fixture.data)
    return path.as_posix()


def _local_query(
    remote_query: str,
    fixtures: Sequence[RemoteFixture],
    tmp_path: Path,
) -> str:
    query = remote_query
    for idx, fixture in enumerate(fixtures):
        query = query.replace(
            fixture.url,
            _local_fixture_path(fixture, tmp_path, f"remote_{idx}"),
        )
    return query


def _native_rows(query: str) -> list[tuple[object, ...]]:
    import duckdb

    connection = duckdb.connect(":memory:")
    try:
        return _rows(connection.sql(query).fetchall())
    finally:
        connection.close()


def _patched_rows(
    query: str,
    fixtures: Sequence[RemoteFixture],
) -> tuple[list[tuple[object, ...]], list[str]]:
    import duckdb

    fixtures_by_url = {fixture.url: fixture for fixture in fixtures}

    def fetch(url: str) -> bytes:
        return fixtures_by_url[url].data

    with (
        mock_pyodide(),
        patch(
            "marimo._runtime._wasm._fetch.fetch_url_bytes",
            side_effect=fetch,
        ) as fetch_url_bytes,
    ):
        patch_result = patch_duckdb_query_for_wasm(query)

    assert patch_result is not None
    assert all(fixture.url not in patch_result.query for fixture in fixtures)

    connection = duckdb.connect(":memory:")
    try:
        for table_name, df in patch_result.tables.items():
            connection.register(table_name, df)
        rows = _rows(connection.sql(patch_result.query).fetchall())
    finally:
        connection.close()

    fetched_urls = [call.args[0] for call in fetch_url_bytes.call_args_list]
    return rows, fetched_urls


def _direct_reader_args(
    case: DirectReadParityCase, source: str
) -> tuple[tuple[object, ...], dict[str, object]]:
    kwargs = dict(case.options)
    if case.source_kwarg is None:
        return (source,), kwargs
    kwargs[case.source_kwarg] = source
    return (), kwargs


def _run_direct_reader(
    case: DirectReadParityCase,
    source: str,
    *,
    api_kind: str,
) -> list[tuple[object, ...]]:
    import duckdb

    args, kwargs = _direct_reader_args(case, source)
    if api_kind == "module":
        relation = getattr(duckdb, case.function_name)(*args, **kwargs)
        return _rows(relation.fetchall())

    connection = duckdb.connect(":memory:")
    try:
        if api_kind == "connection":
            relation = getattr(connection, case.function_name)(*args, **kwargs)
        elif api_kind == "module-connection-kw":
            kwargs["connection"] = connection
            relation = getattr(duckdb, case.function_name)(*args, **kwargs)
        else:
            raise ValueError(f"Unknown DuckDB direct reader API: {api_kind}")
        return _rows(relation.fetchall())
    finally:
        connection.close()


def _patched_direct_rows(
    case: DirectReadParityCase,
    *,
    api_kind: str,
) -> tuple[list[tuple[object, ...]], list[str]]:
    with (
        mock_pyodide(),
        patch(
            "marimo._runtime._wasm._fetch.fetch_url_bytes",
            return_value=case.fixture.data,
        ) as fetch_url_bytes,
    ):
        unpatch = patch_duckdb_for_wasm()
        try:
            rows = _run_direct_reader(
                case, case.fixture.url, api_kind=api_kind
            )
        finally:
            unpatch()

    fetched_urls = [call.args[0] for call in fetch_url_bytes.call_args_list]
    return rows, fetched_urls


def _direct_reader_parity_cases() -> list[DirectReadParityCase]:
    return [
        DirectReadParityCase(
            "csv-positional",
            "read_csv",
            RemoteFixture(
                "https://datasets.marimo.app/cars.csv",
                ".csv",
                b"1;ford\n2;toyota\n",
            ),
            options=(("delimiter", ";"), ("header", False)),
        ),
        DirectReadParityCase(
            "parquet-file-glob",
            "read_parquet",
            RemoteFixture(
                "https://datasets.marimo.app/cars.parquet",
                ".parquet",
                _parquet_bytes("SELECT 'ford' AS make"),
            ),
            source_kwarg="file_glob",
        ),
        DirectReadParityCase(
            "json-path-or-buffer",
            "read_json",
            RemoteFixture(
                "https://datasets.marimo.app/cars.json",
                ".json",
                b'[{"make":"ford"},{"make":"toyota"}]',
            ),
            source_kwarg="path_or_buffer",
            options=(("format", "array"),),
        ),
    ]


def _query_parity_cases() -> list[QueryParityCase]:
    csv = RemoteFixture(
        "https://example.com/cars.csv",
        ".csv",
        b"make,mpg\nford,25\ntoyota,18\n",
    )
    csv_semicolon = RemoteFixture(
        "https://example.com/cars-semicolon.csv",
        ".csv",
        b"1;ford\n2;toyota\n",
    )
    csv_gzip = RemoteFixture(
        "https://example.com/cars.csv.gz",
        ".csv.gz",
        gzip.compress(b"make,mpg\nford,25\n"),
    )
    csv_download = RemoteFixture(
        "https://example.com/download",
        "",
        b"make,mpg\nford,25\n",
    )
    csv_normalize = RemoteFixture(
        "https://example.com/names.csv",
        ".csv",
        b"make name,mpg\nford,25\n",
    )
    tsv = RemoteFixture(
        "https://example.com/walmarts.tsv",
        ".tsv",
        b"longitude\tlatitude\n1\t2\n",
    )
    csv_a = RemoteFixture("https://example.com/a.csv", ".csv", b"a,b\n1,2\n")
    csv_b = RemoteFixture("https://example.com/b.csv", ".csv", b"a,c\n3,4\n")
    parquet = RemoteFixture(
        "https://example.com/a.parquet",
        ".parquet",
        _parquet_bytes(
            """
            SELECT 1 AS a, 'x' AS b
            UNION ALL SELECT 2, 'y'
            """
        ),
    )
    parquet_b = RemoteFixture(
        "https://example.com/b.parquet",
        ".parquet",
        _parquet_bytes("SELECT 3 AS a, 'z' AS b"),
    )
    json_array = RemoteFixture(
        "https://example.com/a.json",
        ".json",
        b'[{"a":1,"b":"x"},{"a":2,"b":"y"}]',
    )
    json_array_b = RemoteFixture(
        "https://example.com/b.json",
        ".json",
        b'[{"a":3,"b":"z"}]',
    )
    complex_json = RemoteFixture(
        "https://example.com/countries.json",
        ".json",
        b'{"type":"Topology","arcs":[[[0]],1]}',
    )
    unstructured_json = RemoteFixture(
        "https://example.com/unstructured.json",
        ".json",
        b'{"a":1} {"a":2}',
    )
    ndjson = RemoteFixture(
        "https://example.com/a.ndjson",
        ".ndjson",
        b'{"a":1}\n{"a":2}\n',
    )
    ndjson_gzip = RemoteFixture(
        "https://example.com/events.ndjson.gz",
        ".ndjson.gz",
        gzip.compress(b'{"event_id":5,"value":10}\n'),
    )
    ndjson_objects_gzip = RemoteFixture(
        "https://example.com/objects.ndjson.gz",
        ".ndjson.gz",
        gzip.compress(b'{"a":1}\n{"a":2}\n'),
    )
    geojson = RemoteFixture(
        "https://example.com/a.geojson",
        ".geojson",
        b'{"type":"FeatureCollection","features":[]}',
    )
    text = RemoteFixture("https://example.com/a.txt", ".txt", b"hello")
    blob = RemoteFixture("https://example.com/a.bin", ".bin", b"\x00\x01")
    return [
        QueryParityCase(
            "direct-csv-literal",
            f"SELECT make, mpg FROM '{csv.url}' ORDER BY make",
            (csv,),
        ),
        QueryParityCase(
            "csv-reader-options",
            f"""
            SELECT column1 FROM read_csv(
                '{csv_semicolon.url}', delim := ';', header := false
            )
            ORDER BY column0
            """,
            (csv_semicolon,),
        ),
        QueryParityCase(
            "tsv-escaped-delimiter",
            f"""
            SELECT * FROM read_csv_auto('{tsv.url}', delim='\\t')
            """,
            (tsv,),
        ),
        QueryParityCase(
            "gzipped-csv",
            f"SELECT make, mpg FROM read_csv('{csv_gzip.url}')",
            (csv_gzip,),
        ),
        QueryParityCase(
            "reader-without-extension",
            f"SELECT make, mpg FROM read_csv('{csv_download.url}')",
            (csv_download,),
        ),
        QueryParityCase(
            "csv-normalize-names",
            f"""
            SELECT make_name, mpg FROM read_csv(
                '{csv_normalize.url}', normalize_names=true
            )
            """,
            (csv_normalize,),
        ),
        QueryParityCase(
            "csv-union-by-name",
            f"""
            SELECT * FROM read_csv(
                ['{csv_a.url}', '{csv_b.url}'], union_by_name=true
            )
            ORDER BY a
            """,
            (csv_a, csv_b),
        ),
        QueryParityCase(
            "parquet-reader",
            f"SELECT * FROM read_parquet('{parquet.url}') ORDER BY a",
            (parquet,),
        ),
        QueryParityCase(
            "parquet-list",
            f"""
            SELECT * FROM read_parquet(['{parquet.url}', '{parquet_b.url}'])
            ORDER BY a
            """,
            (parquet, parquet_b),
        ),
        QueryParityCase(
            "parquet-scan-alias",
            f"SELECT * FROM parquet_scan('{parquet.url}') ORDER BY a",
            (parquet,),
        ),
        QueryParityCase(
            "parquet-direct-literal",
            f"SELECT * FROM '{parquet.url}' ORDER BY a",
            (parquet,),
        ),
        QueryParityCase(
            "json-reader",
            f"SELECT * FROM read_json_auto('{json_array.url}') ORDER BY a",
            (json_array,),
        ),
        QueryParityCase(
            "json-list",
            f"""
            SELECT * FROM read_json_auto(
                ['{json_array.url}', '{json_array_b.url}']
            )
            ORDER BY a
            """,
            (json_array, json_array_b),
        ),
        QueryParityCase(
            "complex-json",
            f"SELECT type, arcs FROM read_json_auto('{complex_json.url}')",
            (complex_json,),
        ),
        QueryParityCase(
            "unstructured-json",
            f"""
            SELECT * FROM read_json(
                '{unstructured_json.url}', format='unstructured'
            )
            ORDER BY a
            """,
            (unstructured_json,),
        ),
        QueryParityCase(
            "ndjson-reader",
            f"SELECT * FROM read_ndjson('{ndjson.url}') ORDER BY a",
            (ndjson,),
        ),
        QueryParityCase(
            "direct-ndjson-literal",
            f"SELECT * FROM '{ndjson.url}' ORDER BY a",
            (ndjson,),
        ),
        QueryParityCase(
            "gzipped-ndjson",
            f"""
            SELECT * FROM read_json(
                '{ndjson_gzip.url}', format='newline_delimited',
                compression='gzip'
            )
            """,
            (ndjson_gzip,),
        ),
        QueryParityCase(
            "ndjson-objects",
            f"SELECT json FROM read_ndjson_objects('{json_array.url}')",
            (json_array,),
        ),
        QueryParityCase(
            "json-objects-auto-gzip",
            f"""
            SELECT json FROM read_json_objects_auto('{ndjson_objects_gzip.url}')
            ORDER BY json
            """,
            (ndjson_objects_gzip,),
        ),
        QueryParityCase(
            "geojson-reader",
            f"SELECT type FROM read_json_auto('{geojson.url}')",
            (geojson,),
        ),
        QueryParityCase(
            "text-and-blob",
            f"""
            SELECT content, size FROM read_text('{text.url}')
            UNION ALL
            SELECT content::VARCHAR, size FROM read_blob('{blob.url}')
            """,
            (text, blob),
        ),
        QueryParityCase(
            "mixed-parquet-json",
            f"""
            SELECT * FROM read_parquet('{parquet.url}')
            UNION ALL
            SELECT * FROM read_json_auto('{json_array.url}')
            ORDER BY a
            """,
            (parquet, json_array),
        ),
    ]


def test_patch_duckdb_for_wasm_noop_outside_pyodide() -> None:
    import duckdb

    original_read_csv = duckdb.read_csv
    original_sql = duckdb.sql
    original_connection_sql = duckdb.DuckDBPyConnection.sql

    unpatch = patch_duckdb_for_wasm()

    assert duckdb.read_csv is original_read_csv
    assert duckdb.sql is original_sql
    assert duckdb.DuckDBPyConnection.sql is original_connection_sql
    unpatch()
    assert duckdb.read_csv is original_read_csv
    assert duckdb.sql is original_sql
    assert duckdb.DuckDBPyConnection.sql is original_connection_sql


class TestDuckDBWasmDirectReadPatch:
    @staticmethod
    def test_patch_installation_does_not_require_sqlglot() -> None:
        import duckdb

        original = duckdb.read_csv
        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._duckdb._require_sqlglot",
                side_effect=AssertionError("sqlglot should be lazy"),
            ),
        ):
            unpatch = patch_duckdb_for_wasm()
            try:
                assert duckdb.read_csv is not original
            finally:
                unpatch()

        assert duckdb.read_csv is original

    @staticmethod
    @pytest.mark.parametrize("api_kind", ["module", "connection"])
    @pytest.mark.parametrize(
        "case",
        _direct_reader_parity_cases(),
        ids=lambda case: case.name,
    )
    def test_direct_readers_match_native_duckdb(
        case: DirectReadParityCase,
        api_kind: str,
        tmp_path: Path,
    ) -> None:
        native_rows = _run_direct_reader(
            case,
            _local_fixture_path(case.fixture, tmp_path, case.name),
            api_kind=api_kind,
        )
        patched_rows, fetched_urls = _patched_direct_rows(
            case, api_kind=api_kind
        )

        assert patched_rows == native_rows
        assert fetched_urls == [case.fixture.url]

    @staticmethod
    @pytest.mark.parametrize(
        "case",
        [
            case
            for case in _direct_reader_parity_cases()
            if case.function_name != "read_csv"
        ],
        ids=lambda case: case.name,
    )
    def test_module_readers_preserve_connection_kw(
        case: DirectReadParityCase, tmp_path: Path
    ) -> None:
        native_rows = _run_direct_reader(
            case,
            _local_fixture_path(case.fixture, tmp_path, case.name),
            api_kind="module-connection-kw",
        )
        patched_rows, fetched_urls = _patched_direct_rows(
            case, api_kind="module-connection-kw"
        )

        assert patched_rows == native_rows
        assert fetched_urls == [case.fixture.url]


class TestDuckDBWasmQueryPatch:
    @staticmethod
    def test_noop_outside_pyodide() -> None:
        assert (
            patch_duckdb_query_for_wasm(
                "SELECT * FROM 'https://datasets.marimo.app/cars.csv'"
            )
            is None
        )

    @staticmethod
    def test_read_parquet_node_preserves_this_argument() -> None:
        from sqlglot import exp

        table = exp.Table(
            this=exp.ReadParquet(
                this=exp.Literal.string("https://example.com/a.parquet")
            )
        )

        source = remote_file_source_from_table(table)

        assert source is not None
        assert source.reader_name == "parquet"
        assert [file.url for file in source.files] == [
            "https://example.com/a.parquet"
        ]

    @staticmethod
    @pytest.mark.parametrize(
        ("query", "expected_source"),
        [
            (
                "SELECT * FROM 'https://example.com/a.csv'",
                True,
            ),
            (
                'SELECT * FROM "https://example.com/a.csv"',
                False,
            ),
            (
                """
                SELECT 1, 'https://example.com/a.csv' AS label
                FROM "https://example.com/a.csv"
                """,
                False,
            ),
        ],
        ids=[
            "direct-literal",
            "double-quoted-identifier",
            "string-literal-and-double-quoted-identifier",
        ],
    )
    def test_token_metadata_fallback_detects_single_quoted_remote_sources(
        query: str,
        expected_source: bool,
    ) -> None:
        from sqlglot import exp

        table = exp.Table(
            this=exp.Identifier(this="https://example.com/a.csv", quoted=True)
        )

        source = remote_file_source_from_table(
            table,
            query=query,
        )

        if not expected_source:
            assert source is None
            return

        assert source is not None
        assert source.reader_name == "csv"
        assert [file.url for file in source.files] == [
            "https://example.com/a.csv"
        ]

    @staticmethod
    @pytest.mark.parametrize(
        "function_name",
        [
            "read_json_objects",
            "read_json_objects_auto",
            "read_ndjson_objects",
        ],
    )
    def test_json_objects_reader_preserves_requested_function(
        monkeypatch: pytest.MonkeyPatch, function_name: str
    ) -> None:
        import duckdb
        import pandas as pd

        from marimo._runtime._wasm._duckdb.dataframe import (
            read_json_objects_dataframe,
        )

        queries: list[str] = []

        class Relation:
            def df(self) -> pd.DataFrame:
                return pd.DataFrame({"json": []})

        def fake_sql(query: str, *, params: list[object]) -> Relation:
            del params
            queries.append(query)
            return Relation()

        monkeypatch.setattr(duckdb, "sql", fake_sql)

        read_json_objects_dataframe(
            b'{"a":1}\n',
            {},
            url="https://example.com/a.json",
            function_name=function_name,
        )

        assert queries == [f"SELECT * FROM {function_name}(?)"]

    @staticmethod
    @pytest.mark.parametrize(
        "case",
        _query_parity_cases(),
        ids=lambda case: case.name,
    )
    def test_rewrites_remote_sources_with_native_duckdb_parity(
        case: QueryParityCase, tmp_path: Path
    ) -> None:
        native_rows = _native_rows(
            _local_query(case.query, case.fixtures, tmp_path)
        )
        patched_rows, fetched_urls = _patched_rows(case.query, case.fixtures)

        assert patched_rows == native_rows
        assert fetched_urls == [fixture.url for fixture in case.fixtures]

    @staticmethod
    def test_list_argument_requires_matching_schemas() -> None:
        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._fetch.fetch_url_bytes",
                side_effect=[b"a,b\n1,2\n", b"a,c\n3,4\n"],
            ),
            pytest.raises(ValueError),
        ):
            patch_duckdb_query_for_wasm(
                """
                SELECT * FROM read_csv([
                    'https://example.com/a.csv',
                    'https://example.com/b.csv'
                ])
                """,
            )

    @staticmethod
    def test_rewrites_direct_geojson_literal() -> None:
        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._fetch.fetch_url_bytes",
                return_value=b'{"type":"FeatureCollection","features":[]}',
            ),
        ):
            patch_result = patch_duckdb_query_for_wasm(
                "FROM 'https://example.com/a.geojson'",
            )

        assert patch_result is not None
        assert (
            patch_result.query == "SELECT * FROM __marimo_wasm_duckdb_remote_0"
        )
        assert _records(next(iter(patch_result.tables.values()))) == [
            {"type": "FeatureCollection", "features": []}
        ]

    @staticmethod
    def test_avoids_reserved_table_names() -> None:
        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._fetch.fetch_url_bytes",
                return_value=b"make,mpg\nford,25\n",
            ),
        ):
            patch_result = patch_duckdb_query_for_wasm(
                "SELECT * FROM 'https://datasets.marimo.app/cars.csv'",
                reserved_names=("__marimo_wasm_duckdb_remote_0",),
            )

        assert patch_result is not None
        assert (
            patch_result.query == "SELECT * FROM __marimo_wasm_duckdb_remote_1"
        )

    @staticmethod
    def test_avoids_sql_cte_table_names_case_insensitively() -> None:
        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._fetch.fetch_url_bytes",
                return_value=b"mpg\n25\n",
            ),
        ):
            patch_result = patch_duckdb_query_for_wasm(
                """
                WITH __MARIMO_WASM_DUCKDB_REMOTE_0 AS (SELECT 99 AS mpg)
                SELECT mpg FROM 'https://datasets.marimo.app/cars.csv'
                """,
            )

        assert patch_result is not None
        assert "FROM __marimo_wasm_duckdb_remote_1" in patch_result.query

    @staticmethod
    def test_does_not_rewrite_create_view_remote_source() -> None:
        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._fetch.fetch_url_bytes",
                return_value=b"make,mpg\nford,25\n",
            ) as fetch_url_bytes,
        ):
            patch_result = patch_duckdb_query_for_wasm(
                """
                CREATE OR REPLACE VIEW remote_cars AS
                SELECT * FROM 'https://datasets.marimo.app/cars.csv'
                """,
            )

        assert patch_result is None
        fetch_url_bytes.assert_not_called()


class TestDuckDBWasmMoSqlIntegration:
    @staticmethod
    async def test_mo_sql_rewrites_remote_literal_in_kernel(
        executing_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._fetch.fetch_url_bytes",
                return_value=b"make,mpg\nford,25\ntoyota,18\n",
            ) as fetch_url_bytes,
            patch.object(
                DuckDBEngine, "sql_output_format", return_value="native"
            ),
        ):
            await executing_kernel.run(
                [
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        """
                        result = mo.sql(
                            '''
                            SELECT make
                            FROM 'https://datasets.marimo.app/cars.csv'
                            WHERE mpg > 20
                            ''',
                            output=False,
                        )
                        """
                    ),
                ]
            )

        result = executing_kernel.globals["result"]
        assert result.fetchall() == [("ford",)]
        fetch_url_bytes.assert_called_once_with(
            "https://datasets.marimo.app/cars.csv"
        )

    @staticmethod
    async def test_mo_sql_create_table_remote_literal_runs_once(
        executing_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._fetch.fetch_url_bytes",
                return_value=b"make,mpg\nford,25\ntoyota,18\n",
            ) as fetch_url_bytes,
            patch.object(
                DuckDBEngine, "sql_output_format", return_value="native"
            ),
        ):
            await executing_kernel.run(
                [
                    exec_req.get("import duckdb"),
                    exec_req.get("import marimo as mo"),
                    exec_req.get(
                        """
                        result = mo.sql(
                            '''
                            CREATE OR REPLACE TABLE __marimo_wasm_create_once AS (
                                SELECT * FROM 'https://datasets.marimo.app/cars.csv'
                            )
                            ''',
                            output=False,
                        )
                        """
                    ),
                    exec_req.get(
                        """
                        rows = duckdb.sql(
                            '''
                            SELECT make, mpg
                            FROM __marimo_wasm_create_once
                            ORDER BY make
                            '''
                        ).fetchall()
                        duckdb.sql("DROP TABLE IF EXISTS __marimo_wasm_create_once")
                        """
                    ),
                ]
            )

        assert executing_kernel.globals["result"] is None
        assert executing_kernel.globals["rows"] == [
            ("ford", 25),
            ("toyota", 18),
        ]
        fetch_url_bytes.assert_called_once_with(
            "https://datasets.marimo.app/cars.csv"
        )


class TestDuckDBWasmSqlUtils:
    @staticmethod
    def test_wrapped_sql_rewrites_remote_literal_with_explicit_connection() -> (
        None
    ):
        import duckdb

        from marimo._sql.utils import wrapped_sql

        connection = duckdb.connect(":memory:")
        try:
            with (
                mock_pyodide(),
                patch(
                    "marimo._runtime._wasm._fetch.fetch_url_bytes",
                    return_value=b"make,mpg\nford,25\ntoyota,18\n",
                ) as fetch_url_bytes,
            ):
                relation = wrapped_sql(
                    """
                    SELECT make
                    FROM 'https://datasets.marimo.app/cars.csv'
                    WHERE mpg > 20
                    """,
                    connection,
                )
                rows = relation.fetchall()
        finally:
            connection.close()

        assert rows == [("ford",)]
        fetch_url_bytes.assert_called_once_with(
            "https://datasets.marimo.app/cars.csv"
        )

    @staticmethod
    def test_execute_duckdb_sql_rewrites_remote_literal_with_explicit_connection() -> (
        None
    ):
        import duckdb

        from marimo._sql.utils import execute_duckdb_sql

        table_name = "__marimo_duckdb_wasm_sql_utils_execute_test"
        connection = duckdb.connect(":memory:")
        try:
            with (
                mock_pyodide(),
                patch(
                    "marimo._runtime._wasm._fetch.fetch_url_bytes",
                    return_value=b"make,mpg\nford,25\ntoyota,18\n",
                ) as fetch_url_bytes,
            ):
                execute_duckdb_sql(
                    f"""
                    CREATE OR REPLACE TABLE {table_name} AS
                    SELECT make
                    FROM 'https://datasets.marimo.app/cars.csv'
                    WHERE mpg > ?
                    """,
                    [20],
                    connection,
                )
                rows = connection.sql(
                    f"SELECT make FROM {table_name} ORDER BY make"
                ).fetchall()
        finally:
            connection.close()

        assert rows == [("ford",)]
        fetch_url_bytes.assert_called_once_with(
            "https://datasets.marimo.app/cars.csv"
        )


class TestDuckDBWasmSqlApiPatch:
    @staticmethod
    def test_module_sql_rewrites_remote_literal_and_preserves_params() -> None:
        import duckdb

        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._fetch.fetch_url_bytes",
                return_value=b"make,mpg\nford,25\ntoyota,18\n",
            ) as fetch_url_bytes,
        ):
            unpatch = patch_duckdb_for_wasm()
            try:
                relation = duckdb.sql(
                    """
                    SELECT make FROM 'https://datasets.marimo.app/cars.csv'
                    WHERE mpg > ?
                    """,
                    params=[20],
                )
            finally:
                unpatch()

        assert relation.fetchall() == [("ford",)]
        fetch_url_bytes.assert_called_once_with(
            "https://datasets.marimo.app/cars.csv"
        )

    @staticmethod
    def test_module_query_rewrites_reader_call() -> None:
        import duckdb

        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._fetch.fetch_url_bytes",
                return_value=b"1;ford\n2;toyota\n",
            ) as fetch_url_bytes,
        ):
            unpatch = patch_duckdb_for_wasm()
            try:
                relation = duckdb.query(
                    """
                    SELECT column1 FROM read_csv(
                        'https://datasets.marimo.app/cars.csv',
                        delim=';', header=false
                    )
                    """
                )
            finally:
                unpatch()

        assert relation.fetchall() == [("ford",), ("toyota",)]
        fetch_url_bytes.assert_called_once_with(
            "https://datasets.marimo.app/cars.csv"
        )

    @staticmethod
    def test_module_query_df_rewrites_reader_call() -> None:
        import duckdb
        import pandas as pd

        local_df = pd.DataFrame({"make": ["ford"], "score": [7]})
        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._fetch.fetch_url_bytes",
                return_value=b"make,mpg\nford,25\ntoyota,18\n",
            ) as fetch_url_bytes,
        ):
            unpatch = patch_duckdb_for_wasm()
            try:
                relation = duckdb.query_df(
                    df=local_df,
                    virtual_table_name="query_df_local",
                    sql_query="""
                    SELECT query_df_local.score, cars.mpg
                    FROM query_df_local
                    JOIN read_csv('https://datasets.marimo.app/cars.csv') AS cars
                    USING (make)
                    """,
                )
                rows = relation.fetchall()
            finally:
                unpatch()
                duckdb.sql("DROP VIEW IF EXISTS query_df_local")

        assert rows == [(7, 25)]
        fetch_url_bytes.assert_called_once_with(
            "https://datasets.marimo.app/cars.csv"
        )

    @staticmethod
    def test_module_query_df_avoids_existing_catalog_table_names() -> None:
        import duckdb
        import pandas as pd

        local_df = pd.DataFrame({"make": ["ford"], "score": [7]})
        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._fetch.fetch_url_bytes",
                return_value=b"make,mpg\nford,25\ntoyota,18\n",
            ),
        ):
            unpatch = patch_duckdb_for_wasm()
            try:
                duckdb.sql(
                    """
                    CREATE OR REPLACE TABLE "__MARIMO_WASM_DUCKDB_REMOTE_0"
                    AS SELECT 'ford' AS make, 99 AS mpg
                    """
                )
                relation = duckdb.query_df(
                    df=local_df,
                    virtual_table_name="query_df_local_collision",
                    sql_query="""
                    SELECT query_df_local_collision.score, cars.mpg
                    FROM query_df_local_collision
                    JOIN read_csv('https://datasets.marimo.app/cars.csv') AS cars
                    USING (make)
                    """,
                )
                rows = relation.fetchall()
            finally:
                unpatch()
                duckdb.sql("DROP VIEW IF EXISTS query_df_local_collision")
                duckdb.sql(
                    'DROP TABLE IF EXISTS "__MARIMO_WASM_DUCKDB_REMOTE_0"'
                )

        assert rows == [(7, 25)]

    @staticmethod
    def test_module_sql_preserves_caller_replacement_scan() -> None:
        import duckdb
        import pandas as pd

        local_df = pd.DataFrame({"x": [1, 2]})
        with mock_pyodide():
            unpatch = patch_duckdb_for_wasm()
            try:
                rows = duckdb.sql("SELECT sum(x) FROM local_df").fetchall()
            finally:
                unpatch()

        assert rows == [(3,)]

    @staticmethod
    def test_module_sql_skips_catalog_lookup_without_remote_source() -> None:
        import duckdb

        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._duckdb._duckdb_catalog_names"
            ) as catalog_names,
        ):
            unpatch = patch_duckdb_for_wasm()
            try:
                rows = duckdb.sql("SELECT 1").fetchall()
            finally:
                unpatch()

        assert rows == [(1,)]
        catalog_names.assert_not_called()

    @staticmethod
    def test_module_sql_without_remote_source_does_not_require_sqlglot() -> (
        None
    ):
        import duckdb

        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._duckdb._require_sqlglot",
                side_effect=AssertionError("sqlglot should be lazy"),
            ),
        ):
            unpatch = patch_duckdb_for_wasm()
            try:
                rows = duckdb.sql("SELECT 1").fetchall()
            finally:
                unpatch()

        assert rows == [(1,)]

    @staticmethod
    def test_module_execute_rewrites_before_side_effects() -> None:
        import duckdb

        table_name = "__marimo_duckdb_wasm_execute_test"
        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._fetch.fetch_url_bytes",
                return_value=b"make,mpg\nford,25\ntoyota,18\n",
            ),
        ):
            unpatch = patch_duckdb_for_wasm()
            try:
                duckdb.execute(
                    f"""
                    CREATE OR REPLACE TABLE {table_name} AS
                    SELECT make FROM 'https://datasets.marimo.app/cars.csv'
                    WHERE mpg > ?
                    """,
                    [20],
                )
                rows = duckdb.sql(
                    f"SELECT make FROM {table_name} ORDER BY make"
                ).fetchall()
            finally:
                unpatch()
                duckdb.sql(f"DROP TABLE IF EXISTS {table_name}")

        assert rows == [("ford",)]

    @staticmethod
    def test_module_execute_creates_table_from_remote_literal() -> None:
        import duckdb

        table_name = "__marimo_duckdb_wasm_execute_create_test"
        with (
            mock_pyodide(),
            patch(
                "marimo._runtime._wasm._fetch.fetch_url_bytes",
                return_value=b"make,mpg\nford,25\ntoyota,18\n",
            ) as fetch_url_bytes,
        ):
            unpatch = patch_duckdb_for_wasm()
            try:
                duckdb.execute(
                    f"""
                    CREATE OR REPLACE TABLE {table_name} AS (
                        SELECT * FROM 'https://datasets.marimo.app/cars.csv'
                    )
                    """
                )
                rows = duckdb.sql(
                    f"SELECT make, mpg FROM {table_name} ORDER BY make"
                ).fetchall()
            finally:
                unpatch()
                duckdb.sql(f"DROP TABLE IF EXISTS {table_name}")

        assert rows == [("ford", 25), ("toyota", 18)]
        fetch_url_bytes.assert_called_once_with(
            "https://datasets.marimo.app/cars.csv"
        )

    @staticmethod
    def test_connection_methods_preserve_caller_replacement_scans() -> None:
        import duckdb
        import pandas as pd

        local_df = pd.DataFrame({"x": [1, 2]})
        connection = duckdb.connect(":memory:")
        try:
            with mock_pyodide():
                unpatch = patch_duckdb_for_wasm()
                try:
                    sql_rows = connection.sql(
                        "SELECT sum(x) FROM local_df"
                    ).fetchall()
                    query_rows = connection.query(
                        "SELECT count(*) FROM local_df"
                    ).fetchall()
                    execute_rows = connection.execute(
                        "SELECT max(x) FROM local_df"
                    ).fetchall()
                finally:
                    unpatch()
        finally:
            connection.close()

        assert sql_rows == [(3,)]
        assert query_rows == [(2,)]
        assert execute_rows == [(2,)]

    @staticmethod
    def test_connection_execute_creates_table_from_remote_literal() -> None:
        import duckdb

        table_name = "__marimo_duckdb_wasm_conn_execute_create_test"
        connection = duckdb.connect(":memory:")
        try:
            with (
                mock_pyodide(),
                patch(
                    "marimo._runtime._wasm._fetch.fetch_url_bytes",
                    return_value=b"make,mpg\nford,25\ntoyota,18\n",
                ) as fetch_url_bytes,
            ):
                unpatch = patch_duckdb_for_wasm()
                try:
                    connection.execute(
                        f"""
                        CREATE OR REPLACE TABLE {table_name} AS (
                            SELECT * FROM 'https://datasets.marimo.app/cars.csv'
                        )
                        """
                    )
                    rows = connection.execute(
                        f"SELECT make, mpg FROM {table_name} ORDER BY make"
                    ).fetchall()
                finally:
                    unpatch()
        finally:
            connection.close()

        assert rows == [("ford", 25), ("toyota", 18)]
        fetch_url_bytes.assert_called_once_with(
            "https://datasets.marimo.app/cars.csv"
        )

    @staticmethod
    def test_connection_sql_joins_caller_local_and_remote_tables() -> None:
        import duckdb
        import pandas as pd

        local_df = pd.DataFrame({"make": ["ford"], "score": [7]})
        connection = duckdb.connect(":memory:")
        try:
            with (
                mock_pyodide(),
                patch(
                    "marimo._runtime._wasm._fetch.fetch_url_bytes",
                    return_value=b"make,mpg\nford,25\ntoyota,18\n",
                ) as fetch_url_bytes,
            ):
                unpatch = patch_duckdb_for_wasm()
                try:
                    relation = connection.sql(
                        """
                        SELECT local_df.score, cars.mpg
                        FROM local_df
                        JOIN read_csv('https://datasets.marimo.app/cars.csv') AS cars
                        USING (make)
                        """
                    )
                    rows = relation.fetchall()
                finally:
                    unpatch()
        finally:
            connection.close()

        assert rows == [(7, 25)]
        fetch_url_bytes.assert_called_once_with(
            "https://datasets.marimo.app/cars.csv"
        )

    @staticmethod
    def test_connection_sql_avoids_existing_catalog_table_names() -> None:
        import duckdb

        connection = duckdb.connect(":memory:")
        try:
            connection.sql(
                """
                CREATE OR REPLACE TABLE "__MARIMO_WASM_DUCKDB_REMOTE_0"
                AS SELECT 99 AS mpg
                """
            )
            with (
                mock_pyodide(),
                patch(
                    "marimo._runtime._wasm._fetch.fetch_url_bytes",
                    return_value=b"mpg\n25\n",
                ) as fetch_url_bytes,
            ):
                unpatch = patch_duckdb_for_wasm()
                try:
                    rows = connection.sql(
                        """
                        SELECT mpg
                        FROM 'https://datasets.marimo.app/cars.csv'
                        """
                    ).fetchall()
                finally:
                    unpatch()
        finally:
            connection.close()

        assert rows == [(25,)]
        fetch_url_bytes.assert_called_once_with(
            "https://datasets.marimo.app/cars.csv"
        )

    @staticmethod
    @pytest.mark.parametrize("api_kind", ["sql", "query", "execute"])
    def test_module_methods_with_connection_avoid_existing_catalog_table_names(
        api_kind: str,
    ) -> None:
        import duckdb

        connection = duckdb.connect(":memory:")
        result_table = "__marimo_duckdb_wasm_module_conn_result"
        try:
            connection.sql(
                """
                CREATE OR REPLACE TABLE "__MARIMO_WASM_DUCKDB_REMOTE_0"
                AS SELECT 99 AS mpg
                """
            )
            with (
                mock_pyodide(),
                patch(
                    "marimo._runtime._wasm._fetch.fetch_url_bytes",
                    return_value=b"mpg\n25\n",
                ) as fetch_url_bytes,
            ):
                unpatch = patch_duckdb_for_wasm()
                try:
                    if api_kind == "execute":
                        duckdb.execute(
                            f"""
                            CREATE OR REPLACE TABLE {result_table} AS
                            SELECT mpg
                            FROM 'https://datasets.marimo.app/cars.csv'
                            """,
                            connection=connection,
                        )
                        rows = connection.sql(
                            f"SELECT mpg FROM {result_table}"
                        ).fetchall()
                    else:
                        rows = getattr(duckdb, api_kind)(
                            """
                            SELECT mpg
                            FROM 'https://datasets.marimo.app/cars.csv'
                            """,
                            connection=connection,
                        ).fetchall()
                finally:
                    unpatch()
        finally:
            connection.close()

        assert rows == [(25,)]
        fetch_url_bytes.assert_called_once_with(
            "https://datasets.marimo.app/cars.csv"
        )

    @staticmethod
    def test_double_quoted_url_table_identifier_is_not_remote_source() -> None:
        import duckdb

        table_name = '"https://datasets.marimo.app/cars.csv"'
        try:
            duckdb.sql(
                f"CREATE OR REPLACE TABLE {table_name} AS SELECT 42 AS x"
            )
            with (
                mock_pyodide(),
                patch(
                    "marimo._runtime._wasm._fetch.fetch_url_bytes",
                    return_value=b"x\n7\n",
                ) as fetch_url_bytes,
            ):
                unpatch = patch_duckdb_for_wasm()
                try:
                    rows = duckdb.sql(f"SELECT x FROM {table_name}").fetchall()
                finally:
                    unpatch()
        finally:
            duckdb.sql(f"DROP TABLE IF EXISTS {table_name}")

        assert rows == [(42,)]
        fetch_url_bytes.assert_not_called()

    @staticmethod
    @mock_pyodide()
    def test_unpatch_restores_module_functions_and_connection_methods() -> (
        None
    ):
        import duckdb

        original_sql = duckdb.sql
        original_query_df = duckdb.query_df
        original_execute = duckdb.execute
        original_connection_sql = duckdb.DuckDBPyConnection.sql
        original_connection_execute = duckdb.DuckDBPyConnection.execute
        original_connection_read_csv = duckdb.DuckDBPyConnection.read_csv
        original_connection_read_parquet = (
            duckdb.DuckDBPyConnection.read_parquet
        )
        original_connection_read_json = duckdb.DuckDBPyConnection.read_json

        unpatch = patch_duckdb_for_wasm()
        assert duckdb.sql is not original_sql
        assert duckdb.query_df is not original_query_df
        assert duckdb.execute is not original_execute
        assert duckdb.DuckDBPyConnection.sql is not original_connection_sql
        assert (
            duckdb.DuckDBPyConnection.execute
            is not original_connection_execute
        )
        assert (
            duckdb.DuckDBPyConnection.read_csv
            is not original_connection_read_csv
        )
        assert (
            duckdb.DuckDBPyConnection.read_parquet
            is not original_connection_read_parquet
        )
        assert (
            duckdb.DuckDBPyConnection.read_json
            is not original_connection_read_json
        )

        unpatch()
        assert duckdb.sql is original_sql
        assert duckdb.query_df is original_query_df
        assert duckdb.execute is original_execute
        assert duckdb.DuckDBPyConnection.sql is original_connection_sql
        assert duckdb.DuckDBPyConnection.execute is original_connection_execute
        assert (
            duckdb.DuckDBPyConnection.read_csv is original_connection_read_csv
        )
        assert (
            duckdb.DuckDBPyConnection.read_parquet
            is original_connection_read_parquet
        )
        assert (
            duckdb.DuckDBPyConnection.read_json
            is original_connection_read_json
        )

        unpatch()

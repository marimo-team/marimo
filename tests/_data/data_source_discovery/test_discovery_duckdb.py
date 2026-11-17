# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import socket
import sys
from types import ModuleType
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

import msgspec
import pytest
from inline_snapshot import snapshot

from marimo._ast.compiler import compile_cell
from marimo._data.data_source_discovery import discover_data_sources
from marimo._data.data_source_discovery.models import DetectedDataSource
from marimo._data.data_source_discovery.plugins.duckdb import discover
from marimo._data.data_source_discovery.types import DiscoveryContext
from marimo._sql.engines.duckdb import DuckDBEngine
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    import duckdb


TOKEN = "synthetic-token'\"\\\nquoted"


def _source(
    environment: dict[str, str], integration: str
) -> DetectedDataSource:
    return next(
        source
        for source in discover(DiscoveryContext(environment=environment))
        if source.id == integration
    )


def _execute(
    source: DetectedDataSource,
    environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    namespace: dict[str, object] = {}
    exec(compile(source.code, "<duckdb-discovery>", "exec"), namespace)
    return namespace


@pytest.fixture
def mocked_connect(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    module = ModuleType("duckdb")
    connect = MagicMock()
    module.__dict__.update(connect=connect, __version__="2.0.0")
    monkeypatch.setitem(sys.modules, "duckdb", module)
    return connect


@pytest.mark.parametrize(
    ("environment", "database"),
    [
        ({"MOTHERDUCK_DATABASE": "analytics"}, "md:analytics"),
        ({"MOTHERDUCK_DATABASE": "md:analytics"}, "md:analytics"),
        ({"DUCKDB_DATABASE": "md:analytics"}, "md:analytics"),
        ({"DUCKDB_DATABASE": "/local/data.duckdb"}, "md:"),
        ({"DUCKDB_DATABASE": "quack:host"}, "md:"),
        (
            {"MOTHERDUCK_DATABASE": "first", "DUCKDB_DATABASE": "md:second"},
            "md:first",
        ),
        ({"MOTHERDUCK_DATABASE": "name'\"\\\nquoted"}, "md:name'\"\\\nquoted"),
        ({}, "md:"),
    ],
)
@pytest.mark.parametrize(
    "token_variable",
    ["MOTHERDUCK_TOKEN", "DUCKDB_MOTHERDUCK_TOKEN", "motherduck_token"],
)
def test_motherduck_routes_database_and_credentials(
    environment: dict[str, str],
    database: str,
    token_variable: str,
    monkeypatch: pytest.MonkeyPatch,
    mocked_connect: MagicMock,
) -> None:
    environment = {**environment, token_variable: TOKEN}
    source = _source(environment, "motherduck-environment")
    namespace = _execute(source, environment, monkeypatch)
    mocked_connect.assert_called_once_with(
        database, config={"motherduck_token": TOKEN}
    )
    assert namespace["motherduck_con"] is mocked_connect.return_value
    assert TOKEN not in source.code


def test_motherduck_uri_without_token(
    monkeypatch: pytest.MonkeyPatch,
    mocked_connect: MagicMock,
) -> None:
    environment = {"DUCKDB_DATABASE": "md:analytics"}
    _execute(
        _source(environment, "motherduck-environment"),
        environment,
        monkeypatch,
    )
    mocked_connect.assert_called_once_with("md:analytics")


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"QUACK_TOKEN": TOKEN},
        {"QUACK_API_KEY": TOKEN},
        {"QUACK_DATABASE": ""},
        {"QUACK_DATABASE": "quack:"},
        {"QUACK_DATABASE": "quack://"},
        {"QUACK_DATABASE": "/local/data.duckdb"},
    ],
)
def test_ignores_incomplete_quack_configuration(
    environment: dict[str, str],
) -> None:
    assert discover(DiscoveryContext(environment=environment)) == []


@pytest.mark.parametrize("token_variable", ["QUACK_TOKEN", "QUACK_API_KEY"])
def test_quack_escapes_runtime_values_and_uses_selected_token(
    token_variable: str,
    monkeypatch: pytest.MonkeyPatch,
    mocked_connect: MagicMock,
) -> None:
    environment = {
        "QUACK_DATABASE": "quack:host'\"\\\nquoted",
        token_variable: TOKEN,
        "DUCKDB_READ_ONLY": "TRUE",
    }
    source = _source(environment, "duckdb-quack-environment")
    namespace = _execute(source, environment, monkeypatch)
    mocked_connect.assert_called_once_with(":memory:")

    def quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    assert mocked_connect.return_value.execute.call_args_list == [
        call("INSTALL quack"),
        call("LOAD quack"),
        call(
            "CREATE TEMPORARY SECRET marimo_quack (TYPE quack, TOKEN "
            + quote(TOKEN)
            + ", SCOPE "
            + quote(environment["QUACK_DATABASE"])
            + ")"
        ),
        call(
            "ATTACH "
            + quote(environment["QUACK_DATABASE"])
            + " AS remote (TYPE quack)"
        ),
        call("USE remote"),
    ]
    assert "_token" not in namespace
    assert TOKEN not in source.code


def test_quack_rejects_unsupported_duckdb_before_connecting(
    monkeypatch: pytest.MonkeyPatch,
    mocked_connect: MagicMock,
) -> None:
    monkeypatch.setattr(sys.modules["duckdb"], "__version__", "1.5.6")
    environment = {"QUACK_DATABASE": "quack:host", "QUACK_TOKEN": TOKEN}
    with pytest.raises(RuntimeError, match=r"require DuckDB 2\.0 or newer"):
        _execute(
            _source(environment, "duckdb-quack-environment"),
            environment,
            monkeypatch,
        )
    mocked_connect.assert_not_called()


def test_quack_missing_token_fails_before_connecting(
    monkeypatch: pytest.MonkeyPatch,
    mocked_connect: MagicMock,
) -> None:
    environment = {"QUACK_DATABASE": "quack:host", "QUACK_TOKEN": TOKEN}
    source = _source(environment, "duckdb-quack-environment")
    environment.pop("QUACK_TOKEN")
    monkeypatch.delenv("QUACK_TOKEN", raising=False)
    with pytest.raises(KeyError, match="QUACK_TOKEN"):
        _execute(source, environment, monkeypatch)
    mocked_connect.assert_not_called()


def test_quack_without_token_uses_existing_duckdb_secret(
    monkeypatch: pytest.MonkeyPatch,
    mocked_connect: MagicMock,
) -> None:
    environment = {"DUCKDB_DATABASE": "quack://host"}
    _execute(
        _source(environment, "duckdb-quack-environment"),
        environment,
        monkeypatch,
    )
    assert mocked_connect.return_value.execute.call_args_list == [
        call("INSTALL quack"),
        call("LOAD quack"),
        call("ATTACH 'quack:host' AS remote (TYPE quack)"),
        call("USE remote"),
    ]


@pytest.mark.parametrize("value", ["1", "TRUE", "yes", "false", "0"])
def test_local_read_only_is_read_at_execution_time(
    value: str,
    monkeypatch: pytest.MonkeyPatch,
    mocked_connect: MagicMock,
) -> None:
    environment = {
        "DUCKDB_PATH": "/local/data.duckdb",
        "DUCKDB_READ_ONLY": "false",
    }
    source = _source(environment, "duckdb-local-environment")
    environment["DUCKDB_READ_ONLY"] = value
    _execute(source, environment, monkeypatch)
    mocked_connect.assert_called_once_with(
        "/local/data.duckdb", read_only=value.lower() in ("1", "true", "yes")
    )


@pytest.mark.requires("duckdb")
def test_local_snippet_opens_file_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import duckdb

    quote = "'" if sys.platform == "win32" else '"'
    path = tmp_path / f"database{quote}quoted.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE calls(n INTEGER); INSERT INTO calls VALUES (42)"
        )
    environment = {"DUCKDB_DATABASE": str(path), "DUCKDB_READ_ONLY": "true"}
    namespace = _execute(
        _source(environment, "duckdb-local-environment"),
        environment,
        monkeypatch,
    )
    con = namespace["duckdb_con"]
    assert isinstance(con, duckdb.DuckDBPyConnection)
    try:
        assert con.execute("SELECT * FROM calls").fetchall() == [(42,)]
        with pytest.raises(duckdb.InvalidInputException, match="read-only"):
            con.execute("INSERT INTO calls VALUES (43)")
    finally:
        con.close()


def test_default_discovery_serializes_only_references() -> None:
    environment = {
        "MOTHERDUCK_TOKEN": TOKEN,
        "MOTHERDUCK_DATABASE": "secret-md-database",
        "DUCKDB_PATH": "/secret/local.duckdb",
        "QUACK_DATABASE": "quack:secret-host",
        "QUACK_API_KEY": "secret-api-key",
        "DUCKDB_READ_ONLY": "TRUE",
    }
    sources = discover_data_sources(environment)
    assert [source.id for source in sources] == snapshot(
        [
            "motherduck-environment",
            "duckdb-quack-environment",
            "duckdb-local-environment",
        ]
    )
    payload = msgspec.json.encode(sources).decode()
    for value in environment.values():
        assert value not in payload
    for source in sources:
        compile_cell(source.code, cell_id=CellId_t("duck"))
    assert msgspec.json.decode(
        msgspec.json.encode(sources[1].configuration)
    ) == snapshot(
        [
            {
                "field": "URI",
                "value": {
                    "kind": "environment-variable",
                    "name": "QUACK_DATABASE",
                },
            },
            {
                "field": "Token",
                "value": {
                    "kind": "environment-variable",
                    "name": "QUACK_API_KEY",
                },
            },
        ]
    )
    assert msgspec.json.decode(
        msgspec.json.encode(sources[1].hides_when)
    ) == snapshot({"kind": "dialect", "substrings": []})


@pytest.fixture(scope="module")
def quack_server() -> Iterator[tuple[str, duckdb.DuckDBPyConnection, str]]:
    extension_directory = os.environ.get(
        "MARIMO_QUACK_TEST_EXTENSION_DIRECTORY"
    )
    if extension_directory is None:
        pytest.skip(
            "Set MARIMO_QUACK_TEST_EXTENSION_DIRECTORY for loopback tests"
        )
    import duckdb

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        uri = f"quack:127.0.0.1:{listener.getsockname()[1]}"
    with duckdb.connect(
        config={"extension_directory": extension_directory}
    ) as server:
        server.execute("LOAD quack; CREATE TABLE calls(n INTEGER)")
        server.execute("CALL quack_serve(?, token=?)", [uri, TOKEN])
        try:
            yield uri, server, extension_directory
        finally:
            server.execute("CALL quack_stop(?)", [uri])


@pytest.mark.parametrize("uri_variable", ["QUACK_DATABASE", "DUCKDB_DATABASE"])
@pytest.mark.parametrize("token_variable", ["QUACK_TOKEN", "QUACK_API_KEY"])
def test_quack_snippet_authenticates_and_discovers_tables(
    quack_server: tuple[str, duckdb.DuckDBPyConnection, str],
    uri_variable: str,
    token_variable: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import duckdb

    uri, server, extension_directory = quack_server
    if uri_variable == "DUCKDB_DATABASE":
        uri = uri.replace("quack:", "quack://", 1)
    environment = {uri_variable: uri, token_variable: TOKEN}
    source = _source(environment, "duckdb-quack-environment")
    connect = duckdb.connect
    with patch.object(
        duckdb,
        "connect",
        side_effect=lambda _: connect(
            config={"extension_directory": extension_directory}
        ),
    ):
        namespace = _execute(source, environment, monkeypatch)
    con = namespace["quack_con"]
    assert isinstance(con, duckdb.DuckDBPyConnection)
    try:
        assert con.execute(
            "SELECT persistent, scope FROM duckdb_secrets() WHERE name = 'marimo_quack'"
        ).fetchall() == [(False, [uri.replace("quack://", "quack:", 1)])]
        engine = DuckDBEngine(con)
        assert (
            engine.get_default_database(),
            engine.get_default_schema(),
        ) == ("remote", "main")
        assert [
            table.name
            for table in engine.get_tables_in_schema(
                schema="main", database="remote", include_table_details=True
            )
        ] == ["calls"]
        with patch.object(
            DuckDBEngine, "sql_output_format", return_value="native"
        ):
            engine.execute("INSERT INTO remote.main.calls VALUES (42)")
        assert server.execute(
            "SELECT count(*) FROM calls WHERE n = 42"
        ).fetchone() == (1,)
        server.execute("DELETE FROM calls")
    finally:
        con.close()


def test_quack_auth_failure_closes_connection(
    quack_server: tuple[str, duckdb.DuckDBPyConnection, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import duckdb

    uri, _, extension_directory = quack_server
    con = duckdb.connect(config={"extension_directory": extension_directory})
    environment = {"QUACK_DATABASE": uri, "QUACK_API_KEY": "incorrect-token"}
    with (
        patch.object(duckdb, "connect", return_value=con),
        pytest.raises(duckdb.Error, match="Authentication") as exc,
    ):
        _execute(
            _source(environment, "duckdb-quack-environment"),
            environment,
            monkeypatch,
        )
    assert "incorrect-token" not in str(exc.value)
    with pytest.raises(duckdb.ConnectionException):
        con.execute("SELECT 1")

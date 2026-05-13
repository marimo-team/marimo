# Copyright 2026 Marimo. All rights reserved.
"""Install WASM-only DuckDB fallbacks for remote file scans.

DuckDB-WASM cannot use ``httpfs``. marimo fetches supported URLs itself,
materializes supported files as pandas DataFrames, then hands those frames
back to DuckDB through replacement scans.

We have two concrete use cases to patch:

* **Direct read methods** — ``duckdb.read_csv/read_parquet/read_json`` are
  wrapped with :class:`WasmPatchSet`. Supported remote URLs are fetched by
  marimo and returned as DuckDB relations.
* **SQL remote scans** — raw DuckDB APIs and marimo's ``mo.sql`` path call the
  same sqlglot rewrite helper. It replaces supported URL scans with generated
  table names and evaluates the original DuckDB call with fetched DataFrames
  in scope so DuckDB replacement scans can resolve them.
"""

from __future__ import annotations

import functools
import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NamedTuple

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime._wasm._duckdb.io import (
    RemoteFileSource,
    remote_file_source_from_reader_args,
)
from marimo._runtime._wasm._duckdb.sources import (
    remote_file_source_from_table,
)
from marimo._runtime._wasm._patches import (
    Unpatch,
    WasmPatchSet,
    WrapperFactory,
)
from marimo._utils.platform import is_pyodide

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    import pandas as pd
    from sqlglot import exp

LOGGER = _loggers.marimo_logger()


class _EvalBindingNames(NamedTuple):
    original: str
    args: str
    kwargs: str


class _SqlApiSpec(NamedTuple):
    query_positional_index: int
    query_keyword_names: tuple[str, ...]


class _DirectReaderSpec(NamedTuple):
    source_keyword_names: tuple[str, ...]


class _DirectReaderCallSpec(NamedTuple):
    source_positional_index: int
    connection_positional_index: int | None


# DuckDB SQL APIs can receive non-string query objects. This sentinel lets us
# tell an omitted query argument apart from a present value such as None.
_MISSING = object()
_SQL_CALL_EXPRESSION = "{original}(*{args}, **{kwargs})"

# The SQL wrappers invoke the original DuckDB callable through eval so DuckDB
# can still see caller-local replacement scans. These are the local binding
# names used for that eval call after collision checks.
_EVAL_BINDING_NAME_BASES = _EvalBindingNames(
    original="__marimo_wasm_duckdb_original",
    args="__marimo_wasm_duckdb_args",
    kwargs="__marimo_wasm_duckdb_kwargs",
)

# Module-level DuckDB SQL functions put the SQL string in different argument
# slots. The specs identify where wrappers should look for the query text.
_MODULE_SQL_FUNCTIONS: dict[str, _SqlApiSpec] = {
    "sql": _SqlApiSpec(
        query_positional_index=0,
        query_keyword_names=("query",),
    ),
    "query": _SqlApiSpec(
        query_positional_index=0,
        query_keyword_names=("query",),
    ),
    "execute": _SqlApiSpec(
        query_positional_index=0,
        query_keyword_names=("query",),
    ),
    "query_df": _SqlApiSpec(
        query_positional_index=2,
        query_keyword_names=("sql_query", "query"),
    ),
}

# Bound connection methods include the connection as args[0], so their query
# argument starts one slot later than the module-level functions.
_CONNECTION_SQL_METHODS: dict[str, _SqlApiSpec] = {
    "sql": _SqlApiSpec(
        query_positional_index=1,
        query_keyword_names=("query",),
    ),
    "query": _SqlApiSpec(
        query_positional_index=1,
        query_keyword_names=("query",),
    ),
    "execute": _SqlApiSpec(
        query_positional_index=1,
        query_keyword_names=("query",),
    ),
}

# Direct reader APIs use reader-specific keyword names for the file source.
_DIRECT_READER_SPECS: dict[str, _DirectReaderSpec] = {
    "read_csv": _DirectReaderSpec(
        source_keyword_names=("path_or_buffer", "source", "file", "path"),
    ),
    "read_parquet": _DirectReaderSpec(
        source_keyword_names=(
            "file_glob",
            "file_globs",
            "source",
            "file",
            "path",
        ),
    ),
    "read_json": _DirectReaderSpec(
        source_keyword_names=("path_or_buffer", "source", "file", "path"),
    ),
}

# Module-level direct readers receive the file source as their first positional
# argument. They may also receive an explicit connection= keyword.
_MODULE_DIRECT_READER_CALL = _DirectReaderCallSpec(
    source_positional_index=0,
    connection_positional_index=None,
)

# Connection direct readers receive the bound connection as args[0], followed
# by the file source as args[1].
_CONNECTION_DIRECT_READER_CALL = _DirectReaderCallSpec(
    source_positional_index=1,
    connection_positional_index=0,
)


@dataclass(frozen=True)
class WasmDuckDBQueryPatch:
    """A rewritten DuckDB query and the DataFrames it references."""

    query: str
    tables: Mapping[str, pd.DataFrame]


@dataclass(frozen=True)
class WasmDuckDBSqlResult:
    """Result of a DuckDB SQL API call that was rewritten for WASM."""

    value: Any


class _RemoteTableNames:
    """Track URL sources and generated table names for one SQL rewrite."""

    def __init__(self, reserved_names: Sequence[str]) -> None:
        self._reserved_names = {
            _duckdb_identifier_key(name) for name in reserved_names
        }
        self._names_by_source: dict[RemoteFileSource, str] = {}

    def __bool__(self) -> bool:
        return bool(self._names_by_source)

    def name_for(self, source: RemoteFileSource) -> str:
        name = self._names_by_source.get(source)
        if name is not None:
            return name

        idx = len(self._names_by_source)
        while True:
            candidate = f"__marimo_wasm_duckdb_remote_{idx}"
            candidate_key = _duckdb_identifier_key(candidate)
            if candidate_key not in self._reserved_names:
                self._names_by_source[source] = candidate
                self._reserved_names.add(candidate_key)
                return candidate
            idx += 1

    def read_dataframes(self) -> dict[str, pd.DataFrame]:
        return {
            table_name: source.read_dataframe()
            for source, table_name in self._names_by_source.items()
        }


def _duckdb_identifier_key(name: str) -> str:
    # DuckDB preserves identifier case but resolves names case-insensitively.
    return name.casefold()


def patch_duckdb_query_for_wasm(
    query: str,
    *,
    statements: Sequence[exp.Expression] | None = None,
    reserved_names: Sequence[str] = (),
) -> WasmDuckDBQueryPatch | None:
    """Replace supported remote file reads with generated table names.

    For example, ``SELECT * FROM read_csv('https://example.com/cars.csv')``
    becomes ``SELECT * FROM __marimo_wasm_duckdb_remote_0`` when suffix ``0``
    is free. The returned ``tables`` mapping binds that name to the fetched
    DataFrame. If the query or ``reserved_names`` already use that identifier,
    the rewriter uses the next free suffix.

    In Pyodide this raises if sqlglot is unavailable and the query may contain
    a remote source. Returns ``None`` when:

    - marimo is not running in Pyodide;
    - the query has no remote URL;
    - the query has no supported remote file source;
    - the query cannot be parsed.
    """
    if not is_pyodide():
        return None

    if statements is None:
        if not _query_may_contain_remote_file_source(query):
            return None
        _require_sqlglot()
        statements = _parse_duckdb_query(query)
    if statements is None:
        return None
    if _contains_remote_view_definition(statements, query=query):
        return None

    table_names = _RemoteTableNames(
        (*reserved_names, *_reserved_sql_names(statements))
    )
    patched_statements = _replace_remote_sources(
        statements, table_names, query=query
    )
    if not table_names:
        return None

    _require_pandas()

    return WasmDuckDBQueryPatch(
        query=_format_duckdb_query(patched_statements, original_query=query),
        tables=table_names.read_dataframes(),
    )


def patch_duckdb_for_wasm() -> Unpatch:
    """Install WASM fallbacks for DuckDB remote file and SQL APIs."""
    if not is_pyodide():
        return lambda: None

    try:
        import duckdb
    except ImportError:
        return lambda: None

    patches = WasmPatchSet()
    for function_name in _DIRECT_READER_SPECS:
        patches.replace(
            duckdb,
            function_name,
            _make_direct_reader_wrapper(
                function_name,
                call_spec=_MODULE_DIRECT_READER_CALL,
            ),
        )
        patches.replace(
            duckdb.DuckDBPyConnection,
            function_name,
            _make_direct_reader_wrapper(
                function_name,
                call_spec=_CONNECTION_DIRECT_READER_CALL,
            ),
        )
    for function_name, spec in _MODULE_SQL_FUNCTIONS.items():
        patches.replace(
            duckdb,
            function_name,
            _make_sql_api_wrapper(
                query_arg_index=spec.query_positional_index,
                query_kwarg_names=spec.query_keyword_names,
            ),
        )
    for method_name, spec in _CONNECTION_SQL_METHODS.items():
        patches.replace(
            duckdb.DuckDBPyConnection,
            method_name,
            _make_sql_api_wrapper(
                query_arg_index=spec.query_positional_index,
                query_kwarg_names=spec.query_keyword_names,
            ),
        )
    return patches.unpatch_all()


def run_duckdb_sql_with_wasm_patch(
    original: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
    *,
    query_arg_index: int,
    query_kwarg_names: tuple[str, ...],
    eval_globals: dict[str, Any],
    eval_locals: Mapping[str, Any],
    reserved_names: Sequence[str] = (),
) -> Any:
    """Run a DuckDB SQL API call after rewriting supported remote scans."""
    wasm_result = try_run_duckdb_sql_with_wasm_patch(
        original,
        args,
        kwargs,
        query_arg_index=query_arg_index,
        query_kwarg_names=query_kwarg_names,
        eval_globals=eval_globals,
        eval_locals=eval_locals,
        reserved_names=reserved_names,
    )
    if wasm_result is not None:
        return wasm_result.value

    kwargs_dict = dict(kwargs)
    binding_names = _eval_binding_names(
        _reserved_namespace_names(
            eval_globals,
            eval_locals,
            (
                *reserved_names,
                *_identifier_string_args(args),
                *_identifier_string_args(tuple(kwargs_dict.values())),
            ),
        )
    )
    return _eval_duckdb_original_call(
        original,
        args,
        kwargs_dict,
        eval_globals=eval_globals,
        eval_locals=eval_locals,
        binding_names=binding_names,
    )


def try_run_duckdb_sql_with_wasm_patch(
    original: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
    *,
    query_arg_index: int,
    query_kwarg_names: tuple[str, ...],
    eval_globals: dict[str, Any],
    eval_locals: Mapping[str, Any],
    reserved_names: Sequence[str] = (),
) -> WasmDuckDBSqlResult | None:
    """Run only if a DuckDB SQL API call needs a WASM rewrite."""
    if not is_pyodide():
        return None

    kwargs_dict = dict(kwargs)
    query = _query_argument(
        args,
        kwargs_dict,
        query_arg_index=query_arg_index,
        query_kwarg_names=query_kwarg_names,
    )
    if not isinstance(query, str):
        return None
    if not _query_may_contain_remote_file_source(query):
        return None

    _require_sqlglot()
    statements = _parse_duckdb_query(query)
    if statements is None or not _contains_supported_remote_source(
        statements, query=query
    ):
        return None
    if _contains_remote_view_definition(statements, query=query):
        return None

    namespace_names = _reserved_namespace_names(
        eval_globals,
        eval_locals,
        (
            *reserved_names,
            *_duckdb_catalog_names(original, args, kwargs_dict),
            *_identifier_string_args(args),
            *_identifier_string_args(tuple(kwargs_dict.values())),
        ),
    )
    binding_names = _eval_binding_names(namespace_names)

    wasm_patch = patch_duckdb_query_for_wasm(
        query,
        statements=statements,
        reserved_names=(
            *namespace_names,
            binding_names.original,
            binding_names.args,
            binding_names.kwargs,
        ),
    )
    if wasm_patch is None:
        return None

    patched_args, patched_kwargs = _replace_query_argument(
        args,
        kwargs_dict,
        patched_query=wasm_patch.query,
        query_arg_index=query_arg_index,
        query_kwarg_names=query_kwarg_names,
    )
    return WasmDuckDBSqlResult(
        _eval_duckdb_original_call(
            original,
            patched_args,
            patched_kwargs,
            eval_globals=eval_globals,
            eval_locals=eval_locals,
            binding_names=binding_names,
            extra_locals=wasm_patch.tables,
        )
    )


def _make_sql_api_wrapper(
    *,
    query_arg_index: int,
    query_kwarg_names: tuple[str, ...],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wrap DuckDB SQL APIs while preserving the caller's local namespace."""

    def _make_wrapper(original: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(original)
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            frame = inspect.currentframe()
            if frame is None or frame.f_back is None:
                return original(*args, **kwargs)
            caller_frame = frame.f_back
            eval_globals = caller_frame.f_globals
            eval_locals = caller_frame.f_locals
            try:
                return run_duckdb_sql_with_wasm_patch(
                    original,
                    args,
                    kwargs,
                    query_arg_index=query_arg_index,
                    query_kwarg_names=query_kwarg_names,
                    eval_globals=eval_globals,
                    eval_locals=eval_locals,
                )
            finally:
                del caller_frame
                del frame

        return _wrapper

    return _make_wrapper


def _query_argument(
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
    *,
    query_arg_index: int,
    query_kwarg_names: tuple[str, ...],
) -> Any:
    """Find the query text without assuming the caller used positional args."""
    if len(args) > query_arg_index:
        return args[query_arg_index]
    for name in query_kwarg_names:
        if name in kwargs:
            return kwargs[name]
    return _MISSING


def _replace_query_argument(
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
    *,
    patched_query: str,
    query_arg_index: int,
    query_kwarg_names: tuple[str, ...],
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Replace the query at the same call site shape used by the caller."""
    kwargs_dict = dict(kwargs)
    if len(args) > query_arg_index:
        patched_args = list(args)
        patched_args[query_arg_index] = patched_query
        return tuple(patched_args), kwargs_dict

    for name in query_kwarg_names:
        if name in kwargs_dict:
            kwargs_dict[name] = patched_query
            return args, kwargs_dict
    return args, kwargs_dict


def _eval_duckdb_original_call(
    original: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
    *,
    eval_globals: dict[str, Any],
    eval_locals: Mapping[str, Any],
    binding_names: _EvalBindingNames,
    extra_locals: Mapping[str, Any] | None = None,
) -> Any:
    """Evaluate the original call where DuckDB can see replacement DataFrames."""
    locals_for_eval = dict(eval_locals)
    if extra_locals is not None:
        locals_for_eval.update(extra_locals)
    locals_for_eval[binding_names.original] = inspect.unwrap(original)
    locals_for_eval[binding_names.args] = args
    locals_for_eval[binding_names.kwargs] = dict(kwargs)

    return eval(
        _SQL_CALL_EXPRESSION.format(
            original=binding_names.original,
            args=binding_names.args,
            kwargs=binding_names.kwargs,
        ),
        eval_globals,
        locals_for_eval,
    )


def _reserved_namespace_names(
    eval_globals: Mapping[str, Any],
    eval_locals: Mapping[str, Any],
    reserved_names: Sequence[str],
) -> tuple[str, ...]:
    names = set(reserved_names)
    names.update(eval_globals)
    names.update(eval_locals)
    return tuple(names)


def _identifier_string_args(args: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple(
        arg for arg in args if isinstance(arg, str) and arg.isidentifier()
    )


def _eval_binding_names(reserved_names: Sequence[str]) -> _EvalBindingNames:
    used = set(reserved_names)
    original = _unused_name(_EVAL_BINDING_NAME_BASES.original, used)
    used.add(original)
    args = _unused_name(_EVAL_BINDING_NAME_BASES.args, used)
    used.add(args)
    kwargs = _unused_name(_EVAL_BINDING_NAME_BASES.kwargs, used)
    return _EvalBindingNames(original=original, args=args, kwargs=kwargs)


def _unused_name(base: str, used: set[str]) -> str:
    if base not in used:
        return base

    idx = 0
    while True:
        candidate = f"{base}_{idx}"
        if candidate not in used:
            return candidate
        idx += 1


def _duckdb_catalog_names(
    original: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
) -> tuple[str, ...]:
    """Reserve existing DuckDB table names before generating replacements."""
    try:
        relation = _show_duckdb_tables(original, args, kwargs)
        rows = relation.fetchall()
    except Exception:
        return ()
    return tuple(str(row[0]) for row in rows if row and row[0] is not None)


def _show_duckdb_tables(
    original: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
) -> Any:
    """Run ``SHOW TABLES`` through the same DuckDB entry point being patched."""
    import duckdb

    original_call = inspect.unwrap(original)
    if args and isinstance(args[0], duckdb.DuckDBPyConnection):
        return inspect.unwrap(type(args[0]).sql)(args[0], "SHOW TABLES")
    connection = kwargs.get("connection")
    if isinstance(connection, duckdb.DuckDBPyConnection):
        return inspect.unwrap(type(connection).sql)(connection, "SHOW TABLES")
    if original_call is inspect.unwrap(duckdb.query_df):
        return inspect.unwrap(duckdb.sql)("SHOW TABLES")
    return original_call("SHOW TABLES")


def _make_direct_reader_wrapper(
    function_name: str,
    *,
    call_spec: _DirectReaderCallSpec,
) -> WrapperFactory:
    def _wrap(original: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(original)
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            source_info = _direct_reader_source(
                function_name,
                args,
                kwargs,
                call_spec=call_spec,
            )
            if source_info is None:
                return original(*args, **kwargs)

            DependencyManager.pandas.require(
                f"to read DuckDB {function_name} sources in WASM"
            )

            source, connection = source_info
            import duckdb

            df = source.read_dataframe()
            if connection is None:
                return duckdb.from_df(df)
            return duckdb.from_df(df, connection=connection)

        return _wrapper

    return _wrap


def _direct_reader_source(
    function_name: str,
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
    *,
    call_spec: _DirectReaderCallSpec,
) -> tuple[RemoteFileSource, Any] | None:
    """Return a remote source only for direct reader calls we can emulate."""
    options = dict(kwargs)
    try:
        source, rest_args = _pop_source_argument(
            function_name,
            args,
            options,
            call_spec=call_spec,
        )
    except TypeError:
        return None
    if rest_args:
        return None

    if call_spec.connection_positional_index is None:
        connection = options.pop("connection", None)
    else:
        connection = args[call_spec.connection_positional_index]
    source_info = remote_file_source_from_reader_args(
        function_name, source, options
    )
    if source_info is None:
        return None
    return source_info, connection


def _pop_source_argument(
    function_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    call_spec: _DirectReaderCallSpec,
) -> tuple[Any, tuple[Any, ...]]:
    """Remove the source argument so remaining kwargs are pure reader options."""
    source_positional_index = call_spec.source_positional_index
    if len(args) > source_positional_index:
        return (
            args[source_positional_index],
            args[source_positional_index + 1 :],
        )

    for key in _DIRECT_READER_SPECS[function_name].source_keyword_names:
        if key in kwargs:
            return kwargs.pop(key), args[source_positional_index + 1 :]

    raise TypeError(f"Missing source argument for duckdb.{function_name}")


def _require_pandas() -> None:
    DependencyManager.pandas.require(
        "to read remote DuckDB file sources in WASM"
    )
    import pandas  # noqa: F401


def _require_sqlglot() -> None:
    DependencyManager.sqlglot.require(
        "to rewrite remote DuckDB SQL sources in WASM"
    )
    import sqlglot  # noqa: F401


def _query_may_contain_remote_file_source(query: str) -> bool:
    return "https://" in query or "http://" in query


def _parse_duckdb_query(query: str) -> list[exp.Expression] | None:
    import sqlglot
    from sqlglot import exp as sqlglot_exp

    try:
        parsed = sqlglot.parse(query, read="duckdb")
    except Exception as e:
        LOGGER.debug("Failed to parse DuckDB query for WASM patch: %s", e)
        return None

    return [
        statement
        for statement in parsed
        if isinstance(statement, sqlglot_exp.Expression)
    ]


def _contains_supported_remote_source(
    statements: Sequence[exp.Expression],
    *,
    query: str,
) -> bool:
    """Check for rewrite work before paying for DuckDB catalog inspection."""
    from sqlglot import exp

    return any(
        remote_file_source_from_table(table, query=query) is not None
        for statement in statements
        for table in statement.find_all(exp.Table)
    )


def _contains_remote_view_definition(
    statements: Sequence[exp.Expression],
    *,
    query: str,
) -> bool:
    """Views persist SQL text, so replacement-scan locals would go stale."""
    from sqlglot import exp

    return any(
        isinstance(statement, exp.Create)
        and str(statement.args.get("kind")).upper() == "VIEW"
        and _contains_supported_remote_source((statement,), query=query)
        for statement in statements
    )


def _replace_remote_sources(
    statements: Sequence[exp.Expression],
    table_names: _RemoteTableNames,
    *,
    query: str,
) -> list[exp.Expression]:
    """Replace supported remote table nodes while preserving aliases."""
    from sqlglot import exp

    def replace_table(node: exp.Expression) -> exp.Expression:
        if not isinstance(node, exp.Table):
            return node

        source = remote_file_source_from_table(node, query=query)
        if source is None:
            return node

        replacement = exp.Table(
            this=exp.to_identifier(table_names.name_for(source))
        )
        alias = node.args.get("alias")
        if alias is not None:
            replacement.set("alias", alias.copy())
        return replacement

    return [
        statement.transform(replace_table, copy=True)
        for statement in statements
    ]


def _reserved_sql_names(
    statements: Sequence[exp.Expression],
) -> tuple[str, ...]:
    """Collect SQL identifiers that generated table names must not shadow."""
    from sqlglot import exp

    names: set[str] = set()
    for statement in statements:
        for identifier in statement.find_all(exp.Identifier):
            if isinstance(identifier.this, str):
                names.add(identifier.this)
        for table in statement.find_all(exp.Table):
            if table.name:
                names.add(table.name)
    return tuple(names)


def _format_duckdb_query(
    statements: Sequence[exp.Expression], *, original_query: str
) -> str:
    """Serialize sqlglot statements without dropping a trailing semicolon."""
    patched_query = "; ".join(
        statement.sql(dialect="duckdb") for statement in statements
    )
    if original_query.rstrip().endswith(";"):
        patched_query += ";"
    return patched_query

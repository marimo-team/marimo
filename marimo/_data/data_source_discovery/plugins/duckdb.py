# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

from marimo._data.data_source_discovery.helpers import (
    ENVIRONMENT_ORIGIN,
    environment_variable,
    has_value,
    hides_when_dialect,
)
from marimo._data.data_source_discovery.models import DetectedDataSource
from marimo._data.data_source_discovery.types import (
    DiscoveryContext,
    DiscoveryPlugin,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

MOTHERDUCK_TOKEN_VARIABLES = (
    "MOTHERDUCK_TOKEN",
    "DUCKDB_MOTHERDUCK_TOKEN",
    "motherduck_token",
)
QUACK_TOKEN_VARIABLES = ("QUACK_TOKEN", "QUACK_API_KEY")

# The DuckDB dialect also matches the always-present in-memory engine.
_NEVER_HIDE = hides_when_dialect()


def _first_configured(
    environment: Mapping[str, str], names: tuple[str, ...]
) -> str | None:
    return next((name for name in names if has_value(environment, name)), None)


def _discover_motherduck(
    environment: Mapping[str, str],
) -> DetectedDataSource | None:
    token_variable = _first_configured(environment, MOTHERDUCK_TOKEN_VARIABLES)
    database_variable = None
    if has_value(environment, "MOTHERDUCK_DATABASE"):
        database_variable = "MOTHERDUCK_DATABASE"
    elif environment.get("DUCKDB_DATABASE", "").startswith("md:"):
        database_variable = "DUCKDB_DATABASE"
    if token_variable is None and database_variable is None:
        return None

    configuration = []
    database = '"md:"'
    if database_variable is not None:
        configuration.append(
            environment_variable("Database", database_variable)
        )
        database = f'os.environ["{database_variable}"]'
        if not environment[database_variable].startswith("md:"):
            database = f'"md:" + {database}'
    token_config = ""
    if token_variable is not None:
        configuration.append(environment_variable("Token", token_variable))
        token_config = (
            f', config={{"motherduck_token": os.environ["{token_variable}"]}}'
        )

    return DetectedDataSource(
        id="motherduck-environment",
        integration="motherduck",
        category="database",
        display_name="MotherDuck",
        confidence="high",
        origins=(ENVIRONMENT_ORIGIN,),
        configuration=tuple(configuration),
        hides_when=_NEVER_HIDE,
        code=(
            "import os\nimport duckdb\n\n"
            f"motherduck_con = duckdb.connect({database}{token_config})"
        ),
    )


def _discover_quack(
    environment: Mapping[str, str],
) -> DetectedDataSource | None:
    database_variable = next(
        (
            name
            for name in ("QUACK_DATABASE", "DUCKDB_DATABASE")
            if environment.get(name, "").startswith("quack:")
            and environment[name].removeprefix("quack:").strip("/")
        ),
        None,
    )
    if database_variable is None:
        return None

    configuration = [environment_variable("URI", database_variable)]
    token_variable = _first_configured(environment, QUACK_TOKEN_VARIABLES)
    token = "None"
    if token_variable is not None:
        configuration.append(environment_variable("Token", token_variable))
        token = f'os.environ["{token_variable}"]'

    return DetectedDataSource(
        id="duckdb-quack-environment",
        integration="duckdb",
        category="database",
        display_name="DuckDB (Quack Protocol)",
        confidence="high",
        origins=(ENVIRONMENT_ORIGIN,),
        configuration=tuple(configuration),
        hides_when=_NEVER_HIDE,
        code=dedent(f'''\
            import os
            import duckdb

            if int(duckdb.__version__.split(".")[0]) < 2:
                raise RuntimeError("Quack connections in marimo require DuckDB 2.0 or newer.")

            _uri = os.environ["{database_variable}"].replace("quack://", "quack:", 1)
            _token = {token}

            def _quote_sql(value: str) -> str:
                return "'" + value.replace("'", "''") + "'"

            quack_con = duckdb.connect(":memory:")
            try:
                quack_con.execute("INSTALL quack")
                quack_con.execute("LOAD quack")
                if _token is not None:
                    quack_con.execute(
                        "CREATE TEMPORARY SECRET marimo_quack (TYPE quack, TOKEN "
                        + _quote_sql(_token) + ", SCOPE " + _quote_sql(_uri) + ")"
                    )
                quack_con.execute("ATTACH " + _quote_sql(_uri) + " AS remote (TYPE quack)")
                quack_con.execute("USE remote")
            except Exception:
                quack_con.close()
                raise
            finally:
                del _token'''),
    )


def _discover_local_duckdb(
    environment: Mapping[str, str],
) -> DetectedDataSource | None:
    database_variable = next(
        (
            name
            for name in ("DUCKDB_PATH", "DUCKDB_DATABASE")
            if has_value(environment, name)
            and not environment[name].startswith(("md:", "quack:"))
        ),
        None,
    )
    if database_variable is None:
        return None

    configuration = [environment_variable("Database Path", database_variable)]
    read_only = ""
    if has_value(environment, "DUCKDB_READ_ONLY"):
        configuration.append(
            environment_variable("Read Only", "DUCKDB_READ_ONLY")
        )
        read_only = (
            ', read_only=os.environ["DUCKDB_READ_ONLY"].lower() '
            'in ("1", "true", "yes")'
        )

    return DetectedDataSource(
        id="duckdb-local-environment",
        integration="duckdb",
        category="database",
        display_name="DuckDB",
        confidence="high",
        origins=(ENVIRONMENT_ORIGIN,),
        configuration=tuple(configuration),
        hides_when=_NEVER_HIDE,
        code=(
            "import os\nimport duckdb\n\n"
            f'duckdb_con = duckdb.connect(os.environ["{database_variable}"]{read_only})'
        ),
    )


def discover(context: DiscoveryContext) -> list[DetectedDataSource]:
    sources = (
        _discover_motherduck(context.environment),
        _discover_quack(context.environment),
        _discover_local_duckdb(context.environment),
    )
    return [source for source in sources if source is not None]


DUCKDB_PLUGIN = DiscoveryPlugin(id="duckdb", discover=discover)

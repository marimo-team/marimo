# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._data.data_source_discovery.helpers import (
    ENVIRONMENT_ORIGIN,
    environment_variable,
    has_value,
)
from marimo._data.data_source_discovery.models import DetectedDataSource
from marimo._data.data_source_discovery.types import (
    DiscoveryContext,
    DiscoveryPlugin,
)

MOTHERDUCK_TOKEN_VARIABLES = ("MOTHERDUCK_TOKEN", "DUCKDB_MOTHERDUCK_TOKEN")
QUACK_TOKEN_VARIABLES = ("QUACK_TOKEN", "QUACK_API_KEY")
DUCKDB_DATABASE_VARIABLES = (
    "DUCKDB_DATABASE",
    "DUCKDB_PATH",
    "QUACK_DATABASE",
)


def discover(context: DiscoveryContext) -> list[DetectedDataSource]:
    environment = context.environment
    detected: list[DetectedDataSource] = []

    # 1. MotherDuck detection (md: protocol)
    motherduck_token_var = next(
        (
            var
            for var in MOTHERDUCK_TOKEN_VARIABLES
            if has_value(environment, var)
        ),
        None,
    )
    if motherduck_token_var is not None:
        configs = [environment_variable("Token", motherduck_token_var)]
        db_name = environment.get("MOTHERDUCK_DATABASE") or environment.get(
            "DUCKDB_DATABASE"
        )
        if db_name:
            configs.append(
                environment_variable(
                    "Database",
                    (
                        "MOTHERDUCK_DATABASE"
                        if "MOTHERDUCK_DATABASE" in environment
                        else "DUCKDB_DATABASE"
                    ),
                )
            )
            connect_str = f"f\"md:{{os.environ['{configs[-1].value.name}']}}\""
        else:
            connect_str = '"md:"'

        detected.append(
            DetectedDataSource(
                id="motherduck-environment",
                integration="motherduck",
                category="database",
                display_name="MotherDuck",
                confidence="high",
                origins=(ENVIRONMENT_ORIGIN,),
                configuration=tuple(configs),
                code=f"""\
import os
import duckdb

con = duckdb.connect({connect_str})""",
            )
        )

    # 2. Quack Protocol detection (quack: / quack:// protocol)
    quack_token_var = next(
        (var for var in QUACK_TOKEN_VARIABLES if has_value(environment, var)),
        None,
    )
    quack_db = environment.get("QUACK_DATABASE")
    duckdb_db = environment.get("DUCKDB_DATABASE", "")
    has_quack_protocol = (
        quack_token_var is not None
        or bool(quack_db)
        or duckdb_db.startswith(("quack:", "quack://"))
    )

    if has_quack_protocol:
        quack_configs = []
        if quack_token_var:
            quack_configs.append(
                environment_variable("Token", quack_token_var)
            )
        if has_value(environment, "QUACK_DATABASE"):
            quack_configs.append(
                environment_variable("Database", "QUACK_DATABASE")
            )
        elif has_value(
            environment, "DUCKDB_DATABASE"
        ) and duckdb_db.startswith(("quack:", "quack://")):
            quack_configs.append(
                environment_variable("Database", "DUCKDB_DATABASE")
            )

        if has_value(environment, "QUACK_DATABASE"):
            connect_arg = 'os.environ["QUACK_DATABASE"]'
        elif has_value(
            environment, "DUCKDB_DATABASE"
        ) and duckdb_db.startswith(("quack:", "quack://")):
            connect_arg = 'os.environ["DUCKDB_DATABASE"]'
        else:
            connect_arg = '"quack:"'

        detected.append(
            DetectedDataSource(
                id="duckdb-quack-environment",
                integration="duckdb",
                category="database",
                display_name="DuckDB (Quack Protocol)",
                confidence="high",
                origins=(ENVIRONMENT_ORIGIN,),
                configuration=tuple(quack_configs),
                code=f"""\
import os
import duckdb

con = duckdb.connect({connect_arg})""",
            )
        )

    # 3. Local DuckDB file database detection
    db_path_var = next(
        (
            var
            for var in ("DUCKDB_PATH", "DUCKDB_DATABASE")
            if has_value(environment, var)
            and not environment.get(var, "").startswith(
                ("md:", "quack:", "quack://")
            )
        ),
        None,
    )
    if db_path_var is not None:
        local_configs = [environment_variable("Database Path", db_path_var)]
        read_only_flag = environment.get("DUCKDB_READ_ONLY", "").lower() in (
            "1",
            "true",
            "yes",
        )
        if has_value(environment, "DUCKDB_READ_ONLY"):
            local_configs.append(
                environment_variable("Read Only", "DUCKDB_READ_ONLY")
            )

        read_only_code = (
            f", read_only={read_only_flag}"
            if has_value(environment, "DUCKDB_READ_ONLY")
            else ""
        )
        detected.append(
            DetectedDataSource(
                id="duckdb-local-environment",
                integration="duckdb",
                category="database",
                display_name="DuckDB",
                confidence="high",
                origins=(ENVIRONMENT_ORIGIN,),
                configuration=tuple(local_configs),
                code=f"""\
import os
import duckdb

con = duckdb.connect(os.environ["{db_path_var}"]{read_only_code})""",
            )
        )

    return detected


DUCKDB_PLUGIN = DiscoveryPlugin(id="duckdb", discover=discover)

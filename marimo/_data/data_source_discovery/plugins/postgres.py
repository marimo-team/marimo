# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._data.data_source_discovery.helpers import (
    ENVIRONMENT_ORIGIN,
    environment_variable,
    has_all,
    has_value,
    is_valid_port,
)
from marimo._data.data_source_discovery.models import DetectedDataSource
from marimo._data.data_source_discovery.types import (
    DiscoveryContext,
    DiscoveryPlugin,
)

REQUIRED = ("PGHOST", "PGUSER", "PGDATABASE")


def discover(context: DiscoveryContext) -> list[DetectedDataSource]:
    environment = context.environment
    if not has_all(environment, REQUIRED):
        return []

    has_valid_port = is_valid_port(environment.get("PGPORT"))
    configuration = [
        environment_variable("Host", "PGHOST"),
        environment_variable("Username", "PGUSER"),
        environment_variable("Database", "PGDATABASE"),
    ]
    if has_valid_port:
        configuration.append(environment_variable("Port", "PGPORT"))
    if has_value(environment, "PGPASSWORD"):
        configuration.append(environment_variable("Password", "PGPASSWORD"))

    port = (
        '    port=int(os.environ["PGPORT"]),'
        if has_valid_port
        else "    port=5432,"
    )
    password = (
        ['    password=os.environ["PGPASSWORD"],']
        if has_value(environment, "PGPASSWORD")
        else []
    )
    code = "\n".join(
        [
            "import os",
            "import sqlalchemy",
            "",
            "DATABASE_URL = sqlalchemy.URL.create(",
            '    "postgresql",',
            '    username=os.environ["PGUSER"],',
            *password,
            '    host=os.environ["PGHOST"],',
            port,
            '    database=os.environ["PGDATABASE"],',
            ")",
            "engine = sqlalchemy.create_engine(DATABASE_URL)",
        ]
    )

    return [
        DetectedDataSource(
            id="postgres-libpq-environment",
            integration="postgres",
            category="database",
            display_name="PostgreSQL",
            confidence="high",
            origins=(ENVIRONMENT_ORIGIN,),
            configuration=tuple(configuration),
            code=code,
        )
    ]


POSTGRES_PLUGIN = DiscoveryPlugin(id="postgres", discover=discover)

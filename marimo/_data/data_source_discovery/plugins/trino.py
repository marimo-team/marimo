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

REQUIRED = ("TRINO_HOST", "TRINO_USER", "TRINO_CATALOG")


def discover(context: DiscoveryContext) -> list[DetectedDataSource]:
    environment = context.environment
    if not has_all(environment, REQUIRED):
        return []

    has_valid_port = is_valid_port(environment.get("TRINO_PORT"))
    configuration = [environment_variable("Host", "TRINO_HOST")]
    if has_valid_port:
        configuration.append(environment_variable("Port", "TRINO_PORT"))
    configuration.append(environment_variable("Username", "TRINO_USER"))
    if has_value(environment, "TRINO_PASSWORD"):
        configuration.append(
            environment_variable("Password", "TRINO_PASSWORD")
        )
    configuration.append(environment_variable("Catalog", "TRINO_CATALOG"))
    if has_value(environment, "TRINO_SCHEMA"):
        configuration.append(environment_variable("Schema", "TRINO_SCHEMA"))

    database = ['database = os.environ["TRINO_CATALOG"]']
    if has_value(environment, "TRINO_SCHEMA"):
        database.append('database += "/" + os.environ["TRINO_SCHEMA"]')
    has_password = has_value(environment, "TRINO_PASSWORD")
    authentication = (
        [
            "connect_args = {",
            '    "auth": BasicAuthentication(',
            '        os.environ["TRINO_USER"],',
            '        os.environ["TRINO_PASSWORD"],',
            "    ),",
            '    "http_scheme": "https",',
            "}",
            "",
        ]
        if has_password
        else []
    )
    port = (
        '    port=int(os.environ["TRINO_PORT"]),'
        if has_valid_port
        else "    port=8080,"
    )
    code = "\n".join(
        [
            "import os",
            "import sqlalchemy",
            "import trino.sqlalchemy",
            *(
                ["from trino.auth import BasicAuthentication"]
                if has_password
                else []
            ),
            "",
            *authentication,
            *database,
            "TRINO_URL = sqlalchemy.URL.create(",
            '    "trino",',
            '    username=os.environ["TRINO_USER"],',
            '    host=os.environ["TRINO_HOST"],',
            port,
            "    database=database,",
            ")",
            (
                "engine = sqlalchemy.create_engine("
                "TRINO_URL, connect_args=connect_args)"
                if has_password
                else "engine = sqlalchemy.create_engine(TRINO_URL)"
            ),
        ]
    )

    return [
        DetectedDataSource(
            id="trino-environment",
            integration="trino",
            category="database",
            display_name="Trino",
            confidence="high",
            origins=(ENVIRONMENT_ORIGIN,),
            configuration=tuple(configuration),
            code=code,
        )
    ]


TRINO_PLUGIN = DiscoveryPlugin(id="trino", discover=discover)

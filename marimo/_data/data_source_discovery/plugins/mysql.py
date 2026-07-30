# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._data.data_source_discovery.helpers import (
    ENVIRONMENT_ORIGIN,
    environment_variable,
    has_all,
    has_value,
)
from marimo._data.data_source_discovery.models import DetectedDataSource
from marimo._data.data_source_discovery.types import (
    DiscoveryContext,
    DiscoveryPlugin,
)

REQUIRED = ("MYSQL_HOST", "MYSQL_USER", "MYSQL_PWD", "MYSQL_DATABASE")


def discover(context: DiscoveryContext) -> list[DetectedDataSource]:
    environment = context.environment
    if not has_all(environment, REQUIRED):
        return []

    configuration = [
        environment_variable("Host", "MYSQL_HOST"),
        environment_variable("Username", "MYSQL_USER"),
        environment_variable("Password", "MYSQL_PWD"),
        environment_variable("Database", "MYSQL_DATABASE"),
    ]
    if has_value(environment, "MYSQL_TCP_PORT"):
        configuration.append(environment_variable("Port", "MYSQL_TCP_PORT"))

    port = (
        '    port=int(os.environ["MYSQL_TCP_PORT"]),'
        if has_value(environment, "MYSQL_TCP_PORT")
        else "    port=3306,"
    )
    code = f"""\
import os
import sqlalchemy

DATABASE_URL = sqlalchemy.URL.create(
    "mysql+pymysql",
    username=os.environ["MYSQL_USER"],
    password=os.environ["MYSQL_PWD"],
    host=os.environ["MYSQL_HOST"],
{port}
    database=os.environ["MYSQL_DATABASE"],
)
engine = sqlalchemy.create_engine(DATABASE_URL)"""

    return [
        DetectedDataSource(
            id="mysql-environment",
            integration="mysql",
            category="database",
            display_name="MySQL",
            confidence="high",
            origins=(ENVIRONMENT_ORIGIN,),
            configuration=tuple(configuration),
            code=code,
        )
    ]


MYSQL_PLUGIN = DiscoveryPlugin(id="mysql", discover=discover)

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

REQUIRED = ("MYSQL_HOST", "MYSQL_USER", "MYSQL_DATABASE")
PASSWORD_VARIABLES = ("MYSQL_PASSWORD", "MYSQL_PWD")


def discover(context: DiscoveryContext) -> list[DetectedDataSource]:
    environment = context.environment
    password_variable = next(
        (name for name in PASSWORD_VARIABLES if has_value(environment, name)),
        None,
    )
    if not has_all(environment, REQUIRED) or password_variable is None:
        return []

    has_valid_port = is_valid_port(environment.get("MYSQL_TCP_PORT"))
    configuration = [
        environment_variable("Host", "MYSQL_HOST"),
        environment_variable("Username", "MYSQL_USER"),
        environment_variable("Password", password_variable),
        environment_variable("Database", "MYSQL_DATABASE"),
    ]
    if has_valid_port:
        configuration.append(environment_variable("Port", "MYSQL_TCP_PORT"))

    port = (
        '    port=int(os.environ["MYSQL_TCP_PORT"]),'
        if has_valid_port
        else "    port=3306,"
    )
    code = f"""\
import os
import sqlalchemy

DATABASE_URL = sqlalchemy.URL.create(
    "mysql+pymysql",
    username=os.environ["MYSQL_USER"],
    password=os.environ["{password_variable}"],
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

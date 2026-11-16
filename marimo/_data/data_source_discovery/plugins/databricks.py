# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

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


def discover(context: DiscoveryContext) -> list[DetectedDataSource]:
    environment = context.environment
    if not has_value(environment, "DATABRICKS_SQL_WAREHOUSE_ID"):
        return []

    configuration = [
        environment_variable("SQL warehouse", "DATABRICKS_SQL_WAREHOUSE_ID")
    ]
    has_profile = has_value(environment, "DATABRICKS_CONFIG_PROFILE")
    if has_profile:
        configuration.append(
            environment_variable("Profile", "DATABRICKS_CONFIG_PROFILE")
        )

    workspace_client = (
        "workspace = WorkspaceClient(\n"
        '    profile=os.environ["DATABRICKS_CONFIG_PROFILE"]\n'
        ")"
        if has_profile
        else "workspace = WorkspaceClient()"
    )
    code = f"""\
import os
from urllib.parse import urlsplit

from databricks import sql
from databricks.sdk import WorkspaceClient

{workspace_client}
connection = sql.connect(
    server_hostname=urlsplit(workspace.config.host).hostname,
    http_path=(
        "/sql/1.0/warehouses/"
        + os.environ["DATABRICKS_SQL_WAREHOUSE_ID"]
    ),
    access_token=workspace.config.authenticate()[
        "Authorization"
    ].removeprefix("Bearer "),
)"""

    return [
        DetectedDataSource(
            id="databricks-sql-warehouse-environment",
            integration="databricks",
            category="database",
            display_name="Databricks SQL warehouse",
            confidence="high",
            origins=(ENVIRONMENT_ORIGIN,),
            configuration=tuple(configuration),
            code=code,
            hides_when=hides_when_dialect("databricks"),
        )
    ]


DATABRICKS_PLUGIN = DiscoveryPlugin(id="databricks", discover=discover)

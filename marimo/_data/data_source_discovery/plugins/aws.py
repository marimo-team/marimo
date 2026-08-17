# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._data.data_source_discovery.helpers import (
    ENVIRONMENT_ORIGIN,
    environment_variable,
    has_all,
    has_value,
)
from marimo._data.data_source_discovery.models import (
    DetectedDataSource,
    DetectedDataSourceConfiguration,
)
from marimo._data.data_source_discovery.types import (
    DiscoveryContext,
    DiscoveryPlugin,
)

ACCESS_KEYS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
OPTIONAL_VARIABLES = (
    ("Session token", "AWS_SESSION_TOKEN"),
    ("Region", "AWS_DEFAULT_REGION"),
    ("Region", "AWS_REGION"),
    ("Profile", "AWS_PROFILE"),
    ("Endpoint", "AWS_ENDPOINT_URL"),
    ("S3 endpoint", "AWS_ENDPOINT_URL_S3"),
)


def discover(context: DiscoveryContext) -> list[DetectedDataSource]:
    environment = context.environment
    has_access_keys = has_all(environment, ACCESS_KEYS)
    has_profile = has_value(environment, "AWS_PROFILE")
    if not has_access_keys and not has_profile:
        return []

    configuration: list[DetectedDataSourceConfiguration] = []
    if has_access_keys:
        configuration.extend(
            (
                environment_variable("Access key ID", "AWS_ACCESS_KEY_ID"),
                environment_variable(
                    "Secret access key", "AWS_SECRET_ACCESS_KEY"
                ),
            )
        )
    for field, name in OPTIONAL_VARIABLES:
        if has_value(environment, name):
            configuration.append(environment_variable(field, name))

    has_custom_endpoint = has_value(
        environment, "AWS_ENDPOINT_URL"
    ) or has_value(environment, "AWS_ENDPOINT_URL_S3")
    return [
        DetectedDataSource(
            id="aws-s3-environment",
            integration="aws",
            category="object-storage",
            display_name=(
                "S3-compatible storage" if has_custom_endpoint else "Amazon S3"
            ),
            confidence="high",
            origins=(ENVIRONMENT_ORIGIN,),
            configuration=tuple(configuration),
            code="""\
import s3fs

# Uses the standard AWS credential and endpoint environment variables.
fs = s3fs.S3FileSystem()""",
        )
    ]


AWS_PLUGIN = DiscoveryPlugin(id="aws", discover=discover)

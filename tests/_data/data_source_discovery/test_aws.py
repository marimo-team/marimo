# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec
from inline_snapshot import snapshot

from marimo._data.data_source_discovery.models import (
    EnvironmentVariableDiscoveryValue,
)
from marimo._data.data_source_discovery.plugins.aws import discover
from marimo._data.data_source_discovery.types import DiscoveryContext


def test_discovers_s3_compatible_environment() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "AWS_ACCESS_KEY_ID": "secret-access-key",
                "AWS_SECRET_ACCESS_KEY": "secret-secret-key",
                "AWS_ENDPOINT_URL_S3": "https://example.invalid",
                "AWS_REGION": "us-east-1",
            }
        )
    )

    builtins = msgspec.json.decode(msgspec.json.encode(detected))
    assert builtins == snapshot(
        [
            {
                "id": "aws-s3-environment",
                "integration": "aws",
                "category": "object-storage",
                "displayName": "S3-compatible storage",
                "confidence": "high",
                "origins": [
                    {
                        "type": "environment",
                        "label": "Kernel environment",
                    }
                ],
                "configuration": [
                    {
                        "field": "Access key ID",
                        "value": {
                            "kind": "environment-variable",
                            "name": "AWS_ACCESS_KEY_ID",
                        },
                    },
                    {
                        "field": "Secret access key",
                        "value": {
                            "kind": "environment-variable",
                            "name": "AWS_SECRET_ACCESS_KEY",
                        },
                    },
                    {
                        "field": "Region",
                        "value": {
                            "kind": "environment-variable",
                            "name": "AWS_REGION",
                        },
                    },
                    {
                        "field": "S3 endpoint",
                        "value": {
                            "kind": "environment-variable",
                            "name": "AWS_ENDPOINT_URL_S3",
                        },
                    },
                ],
                "code": """\
import s3fs

# Uses the standard AWS credential and endpoint environment variables.
fs = s3fs.S3FileSystem()""",
                "configured": False,
            }
        ]
    )
    assert "secret-" not in repr(builtins)


def test_discovers_profile_without_access_keys() -> None:
    detected = discover(
        DiscoveryContext(environment={"AWS_PROFILE": "secret-profile"})
    )

    assert msgspec.json.decode(
        msgspec.json.encode(detected[0].configuration)
    ) == snapshot(
        [
            {
                "field": "Profile",
                "value": {
                    "kind": "environment-variable",
                    "name": "AWS_PROFILE",
                },
            }
        ]
    )


def test_ignores_incomplete_access_keys() -> None:
    detected = discover(
        DiscoveryContext(environment={"AWS_ACCESS_KEY_ID": "secret"})
    )

    assert detected == snapshot([])


def test_ignores_empty_profile_and_endpoint() -> None:
    assert discover(
        DiscoveryContext(environment={"AWS_PROFILE": ""})
    ) == snapshot([])

    detected = discover(
        DiscoveryContext(
            environment={
                "AWS_PROFILE": "secret-profile",
                "AWS_ENDPOINT_URL_S3": "",
            }
        )
    )
    assert detected[0].display_name == snapshot("Amazon S3")
    assert [
        item.value.name
        for item in detected[0].configuration
        if isinstance(item.value, EnvironmentVariableDiscoveryValue)
    ] == snapshot(["AWS_PROFILE"])

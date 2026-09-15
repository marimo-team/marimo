# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec
from inline_snapshot import snapshot

from marimo._data.data_source_discovery.models import (
    EnvironmentVariableDiscoveryValue,
)
from marimo._data.data_source_discovery.plugins.huggingface import discover
from marimo._data.data_source_discovery.types import DiscoveryContext


def test_discovers_hf_token() -> None:
    detected = discover(
        DiscoveryContext(environment={"HF_TOKEN": "hf_secret-token"})
    )

    builtins = msgspec.json.decode(
        msgspec.json.encode(detected), type=list[dict[str, object]]
    )
    assert builtins == snapshot(
        [
            {
                "id": "huggingface-hub-environment",
                "integration": "huggingface",
                "category": "object-storage",
                "displayName": "Hugging Face Hub",
                "confidence": "high",
                "origins": [
                    {
                        "type": "environment",
                        "label": "Kernel environment",
                    }
                ],
                "configuration": [
                    {
                        "field": "Token",
                        "value": {
                            "kind": "environment-variable",
                            "name": "HF_TOKEN",
                        },
                    },
                ],
                "code": """\
from huggingface_hub import HfApi

hf = HfApi()""",
                "hidesWhen": {
                    "kind": "storage",
                    "protocols": ["hf"],
                    "backendTypes": ["huggingface"],
                },
            }
        ]
    )
    assert "secret-" not in repr(builtins)


def test_discovers_legacy_token_variable() -> None:
    detected = discover(
        DiscoveryContext(
            environment={"HUGGING_FACE_HUB_TOKEN": "hf_secret-token"}
        )
    )

    assert [
        item.value.name
        for item in detected[0].configuration
        if isinstance(item.value, EnvironmentVariableDiscoveryValue)
    ] == snapshot(["HUGGING_FACE_HUB_TOKEN"])


def test_prefers_hf_token_over_legacy_variable() -> None:
    detected = discover(
        DiscoveryContext(
            environment={
                "HF_TOKEN": "new-token",
                "HUGGING_FACE_HUB_TOKEN": "legacy-token",
            }
        )
    )

    assert [
        item.value.name
        for item in detected[0].configuration
        if isinstance(item.value, EnvironmentVariableDiscoveryValue)
    ] == snapshot(["HF_TOKEN"])


def test_ignores_missing_token() -> None:
    assert discover(DiscoveryContext(environment={})) == snapshot([])


def test_ignores_empty_token() -> None:
    assert discover(
        DiscoveryContext(environment={"HF_TOKEN": ""})
    ) == snapshot([])

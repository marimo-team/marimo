# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import subprocess
from typing import Any

import yaml


def _normalize_union_order(schema: Any) -> Any:
    if isinstance(schema, list):
        return [_normalize_union_order(value) for value in schema]
    if isinstance(schema, dict):
        result = {
            key: _normalize_union_order(value) for key, value in schema.items()
        }
        # msgspec versions can emit equivalent union alternatives in a different order.
        for key in ("anyOf", "oneOf"):
            if isinstance(result.get(key), list):
                result[key] = sorted(
                    result[key],
                    key=lambda value: json.dumps(value, sort_keys=True),
                )
        return result
    return schema


def test_cli_development_openapi() -> None:
    p = subprocess.run(
        ["marimo", "development", "openapi"],
        capture_output=True,
    )
    assert p.returncode == 0
    # Check a random endpoint
    assert "/api/export/html" in p.stdout.decode()


def test_openapi_up_to_date() -> None:
    with open("packages/openapi/api.yaml") as f:
        current_content = yaml.safe_load(f)

    result = subprocess.run(
        ["marimo", "development", "openapi"], capture_output=True, text=True
    )
    generated_content = yaml.safe_load(result.stdout)

    # Remove the version from both contents
    # we don't care about the version for this comparison
    if "info" in current_content:
        current_content["info"].pop("version", None)
    if "info" in generated_content:
        generated_content["info"].pop("version", None)

    cmd = "marimo development openapi > packages/openapi/api.yaml && make fe-codegen"
    assert _normalize_union_order(current_content) == _normalize_union_order(
        generated_content
    ), (
        f"packages/openapi/api.yaml is not up to date. Run '{cmd}' to update it."
    )

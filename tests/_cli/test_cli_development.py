# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess

import yaml

from marimo._cli.development.commands import _generate_server_api_schema


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
    assert current_content == generated_content, (
        f"packages/openapi/api.yaml is not up to date. Run '{cmd}' to update it."
    )


def test_table_filter_openapi_contract() -> None:
    schema = _generate_server_api_schema()
    endpoint = schema["paths"]["/api/ai/table-filter"]["post"]
    request_body = endpoint["requestBody"]["content"]["application/json"]
    response_body = endpoint["responses"][200]["content"]["application/json"]
    assert request_body["schema"] == {
        "$ref": "#/components/schemas/AiTableFilterRequest"
    }
    assert response_body["schema"] == {
        "$ref": "#/components/schemas/AiTableFilterResponse"
    }
    assert endpoint["parameters"] == [
        {
            "in": "header",
            "name": "Marimo-Session-Id",
            "schema": {"type": "string"},
            "required": True,
        }
    ]
    models = schema["components"]["schemas"]
    request = models["AiTableFilterRequest"]
    response = models["AiTableFilterResponse"]
    assert request["required"] == ["request", "context"]
    assert request["properties"] == {
        "request": {"type": "string"},
        "context": {"$ref": "#/components/schemas/FilterContext"},
    }
    assert response["required"] == ["fql", "explanation", "aliases"]
    assert response["properties"] == {
        "fql": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "explanation": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "aliases": {
            "type": "array",
            "items": {"$ref": "#/components/schemas/TableFilterAlias"},
        },
    }
    assert models["FilterContext"]["properties"]["columns"] == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/FilterContextColumn"},
    }
    assert models["TableFilterAlias"]["properties"] == {
        "name": {"type": "string"},
        "alias": {"type": "string"},
    }

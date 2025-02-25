# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import subprocess

import yaml


def test_cli_development_openapi() -> None:
    p = subprocess.run(
        ["marimo", "development", "openapi"],
        capture_output=True,
    )
    assert p.returncode == 0
    # Check a random endpoint
    assert "/api/export/html" in p.stdout.decode()


def test_openapi_up_to_date() -> None:
    with open("openapi/api.yaml") as f:
        current_content = yaml.safe_load(f)

    result = subprocess.run(
        ["marimo", "development", "openapi"], capture_output=True, text=True
    )
    generated_content = yaml.safe_load(result.stdout)

    # Remove the version from both contents
    # we don't care about the version for this comparison
    if "info" in current_content:
        del current_content["info"]["version"]
    if "info" in generated_content:
        del generated_content["info"]["version"]

    cmd = "marimo development openapi > openapi/api.yaml && make fe-codegen"
    assert current_content == generated_content, (
        f"openapi/api.yaml is not up to date. Run '{cmd}' to update it."
    )

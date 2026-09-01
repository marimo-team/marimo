# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "marimo_pair_v0_0_19"
JSON_FIXTURES = (
    "manifest.json",
    "registry.json",
    "discover-output.json",
    "sessions.json",
    "execute-request.json",
)
EXPECTED_MANIFEST = {
    "repository": "https://github.com/marimo-team/marimo-pair",
    "release": "v0.0.19",
    "commit": "de98ee4e268df1b44fa777f360aa58e241a7a635",
    "discover_script_sha256": (
        "e0b43ba5effe5f7e66e3c60fda4db7950b76feed8a72c082d5f8ded9769dc090"
    ),
    "execute_script_sha256": (
        "fb7e4d3a0e94af53a065b5fd5f4a7601d19db25a0ddeef74ea8b73ab09274631"
    ),
    "required_first_command": "import marimo._code_mode as cm; help(cm)",
}


@pytest.mark.parametrize("filename", JSON_FIXTURES)
def test_json_fixture_is_valid(filename: str) -> None:
    json.loads((FIXTURE_DIR / filename).read_text())


def test_manifest_records_frozen_baseline() -> None:
    manifest = json.loads((FIXTURE_DIR / "manifest.json").read_text())
    assert manifest == EXPECTED_MANIFEST


@pytest.mark.parametrize(
    "filename", ["execute-success.sse", "execute-failure.sse"]
)
def test_sse_fixture_ends_with_one_done_event(filename: str) -> None:
    body = (FIXTURE_DIR / filename).read_text()
    records = body.rstrip("\n").split("\n\n")

    assert body.endswith("\n\n")
    assert sum(record.startswith("event: done\n") for record in records) == 1
    assert records[-1].startswith("event: done\n")
